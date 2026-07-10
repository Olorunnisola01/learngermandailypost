"""
extract_cookies.py — Extract Chrome Profile 12 cookies for Steel.dev.
Run AFTER closing Chrome (or at least ensuring Profile 12 is not active).
"""
import base64, json, os, shutil, sqlite3, subprocess, sys
import win32crypt
from Crypto.Cipher import AES

CHROME_USER_DATA = r"C:\Users\ADELEKEOLORUNISOLAO\AppData\Local\Google\Chrome\User Data"
PROFILE          = "Profile 12"
PROFILE_DIR      = os.path.join(CHROME_USER_DATA, PROFILE)
LOCAL_STATE      = os.path.join(CHROME_USER_DATA, "Local State")
DB_COPY          = r"C:\Users\ADELEKEOLORUNISOLAO\AppData\Local\Temp\yt_cookies_german.db"
REPO_DIR         = r"C:\Users\ADELEKEOLORUNISOLAO\Desktop\learngermandailypost"
GITHUB_REPO      = "Olorunnisola01/learngermandailypost"

def get_aes_key():
    with open(LOCAL_STATE, encoding="utf-8") as f:
        ls = json.load(f)
    enc = base64.b64decode(ls["os_crypt"]["encrypted_key"])[5:]  # strip 5-byte "DPAPI" header
    return win32crypt.CryptUnprotectData(enc, None, None, None, 0)[1]

def decrypt_cookie(key, encrypted_value):
    if encrypted_value[:3] in (b"v10", b"v20"):
        nonce = encrypted_value[3:15]
        ct    = encrypted_value[15:-16]
        tag   = encrypted_value[-16:]
        try:
            plain = AES.new(key, AES.MODE_GCM, nonce=nonce).decrypt_and_verify(ct, tag)
            return plain.decode("utf-8", errors="replace")  # No 32-byte prefix for Chrome
        except Exception:
            return None
    else:
        try:
            raw = win32crypt.CryptUnprotectData(encrypted_value, None, None, None, 0)[1]
            return raw.decode("utf-8", errors="replace")
        except Exception:
            return None

def main():
    cookies_src = os.path.join(PROFILE_DIR, "Default", "Cookies")
    if not os.path.exists(cookies_src):
        # Some profiles store directly under profile, not Default subfolder
        cookies_src = os.path.join(PROFILE_DIR, "Cookies")
    if not os.path.exists(cookies_src):
        print(f"ERROR: Cookies file not found at {cookies_src}")
        sys.exit(1)

    print(f"Copying cookies from: {cookies_src}")
    shutil.copy2(cookies_src, DB_COPY)
    key = get_aes_key()

    conn = sqlite3.connect(DB_COPY)
    cur  = conn.cursor()
    cur.execute("""
        SELECT host_key, path, name, encrypted_value, expires_utc, is_secure, is_httponly, samesite
        FROM cookies
        WHERE host_key LIKE '%youtube.com' OR host_key LIKE '%google.com'
        ORDER BY host_key, name
    """)
    rows = cur.fetchall()
    conn.close()

    samesite_map = {-1: "None", 0: "None", 1: "Lax", 2: "Strict"}
    cookies = []
    for host_key, path, name, ev, expires_utc, is_secure, is_httponly, samesite in rows:
        value = decrypt_cookie(key, ev)
        if value is None:
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

    ctx = {"cookies": cookies, "origins": []}
    out = os.path.join(REPO_DIR, "data", "steel_context.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(ctx, f, ensure_ascii=True, indent=2)
    print(f"Saved {len(cookies)} cookies to {out}")

    # Push to GitHub secret via stdin (avoids WinError 206 on long values)
    with open(out, "rb") as f:
        result = subprocess.run(
            ["gh", "secret", "set", "STEEL_SESSION_CONTEXT", "--repo", GITHUB_REPO],
            stdin=f, capture_output=True, text=True
        )
    if result.returncode == 0:
        print("Secret STEEL_SESSION_CONTEXT saved to GitHub!")
    else:
        print(f"gh secret set failed: {result.stderr}")
        print("Save it manually from:", out)

if __name__ == "__main__":
    main()
