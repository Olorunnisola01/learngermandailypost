"""
extract_cookies.py
Extracts YouTube/Google cookies from ixBrowser Profile 10 (Learn German Without Stress).
ixBrowser uses v10 AES-GCM encryption with a 32-byte prefix after decryption.
Run with ixBrowser Profile 10 CLOSED.
"""
import base64, json, os, shutil, sqlite3, subprocess, sys
import win32crypt
from Crypto.Cipher import AES

PROFILE_DATA = r"C:\Users\ADELEKEOLORUNISOLAO\AppData\Roaming\ixBrowser\Browser Data\6de0cc60e340fde4ae3b817082db09dd"
LOCAL_STATE  = os.path.join(PROFILE_DATA, "Local State")
COOKIES_SRC  = os.path.join(PROFILE_DATA, "Default", "Network", "Cookies")
DB_COPY      = r"C:\Users\ADELEKEOLORUNISOLAO\AppData\Local\Temp\ix10_cookies.db"
REPO_DIR     = r"C:\Users\ADELEKEOLORUNISOLAO\Desktop\learngermandailypost"
GITHUB_REPO  = "Olorunnisola01/learngermandailypost"


def get_aes_key():
    with open(LOCAL_STATE, encoding="utf-8") as f:
        ls = json.load(f)
    enc = base64.b64decode(ls["os_crypt"]["encrypted_key"])[5:]  # strip "DPAPI" header
    return win32crypt.CryptUnprotectData(enc, None, None, None, 0)[1]


def decrypt_cookie(key, ev):
    if ev[:3] in (b"v10", b"v20"):
        nonce = ev[3:15]
        ct    = ev[15:-16]
        tag   = ev[-16:]
        try:
            plain = AES.new(key, AES.MODE_GCM, nonce=nonce).decrypt_and_verify(ct, tag)
            # ixBrowser adds a 32-byte prefix — strip it
            return plain[32:].decode("utf-8", errors="replace")
        except Exception:
            return None
    else:
        try:
            return win32crypt.CryptUnprotectData(ev, None, None, None, 0)[1].decode("utf-8", errors="replace")
        except Exception:
            return None


def main():
    if not os.path.exists(COOKIES_SRC):
        print(f"ERROR: Cookies not found at {COOKIES_SRC}")
        sys.exit(1)

    print(f"Copying cookies from: {COOKIES_SRC}")
    shutil.copy2(COOKIES_SRC, DB_COPY)

    key = get_aes_key()

    conn = sqlite3.connect(DB_COPY)
    cur  = conn.cursor()
    cur.execute("""
        SELECT host_key, path, name, encrypted_value, expires_utc, is_secure, is_httponly, samesite
        FROM cookies
        WHERE host_key LIKE '%youtube.com%' OR host_key LIKE '%google.com%'
        ORDER BY host_key, name
    """)
    rows = cur.fetchall()
    conn.close()

    samesite_map = {-1: "None", 0: "None", 1: "Lax", 2: "Strict"}
    cookies = []
    for host_key, path, name, ev, expires_utc, is_secure, is_httponly, samesite in rows:
        value = decrypt_cookie(key, ev)
        if not value:
            continue
        unix_ts = (expires_utc / 1_000_000) - 11644473600 if expires_utc and expires_utc > 0 else None
        c = {
            "name":     name,
            "value":    value,
            "domain":   host_key,
            "path":     path,
            "httpOnly": bool(is_httponly),
            "secure":   bool(is_secure),
            "sameSite": samesite_map.get(samesite, "Lax"),
        }
        if unix_ts and unix_ts > 0:
            c["expires"] = int(unix_ts)
        cookies.append(c)

    print(f"Decrypted {len(cookies)} cookies")

    ctx = {"cookies": cookies, "origins": []}
    out = os.path.join(REPO_DIR, "data", "steel_context.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(ctx, f, ensure_ascii=True, indent=2)
    print(f"Saved to {out}")

    with open(out, "rb") as f:
        result = subprocess.run(
            ["gh", "secret", "set", "STEEL_SESSION_CONTEXT", "--repo", GITHUB_REPO],
            stdin=f, capture_output=True, text=True
        )
    if result.returncode == 0:
        print("SUCCESS: STEEL_SESSION_CONTEXT secret saved to GitHub!")
    else:
        print(f"gh secret set failed: {result.stderr}")
        print(f"Manual fallback: gh secret set STEEL_SESSION_CONTEXT --repo {GITHUB_REPO} < {out}")


if __name__ == "__main__":
    main()
