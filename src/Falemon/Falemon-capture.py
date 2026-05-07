import subprocess, os, time, shutil, re, ctypes, urllib.request

FALEMON_DIR = r"C:\Falemon" if os.path.exists(r"C:\Falemon\Falemon.exe") \
    else r"c:\Users\Administrator\Downloads\Falemon\extracted_app"
FALEMON_EXE = os.path.join(FALEMON_DIR, "Falemon.exe")
CAPTURE_DIR = r"C:\captured"
os.makedirs(CAPTURE_DIR, exist_ok=True)

PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
kernel32 = ctypes.windll.kernel32

SUB_SUFFIXES = ['chr', 'chY', 'lon', 'qxY', 'sfd', 'sg4', 'vrn']


def start_falemon():
    return subprocess.Popen([FALEMON_EXE], cwd=FALEMON_DIR)


def scan_memory(pid):
    patterns = [
        rb'https?://api\d+\.qsvtm\.com/[A-Za-z0-9_/]{10,150}',
        rb'api\d+\.qsvtm\.com/[A-Za-z0-9_]+/[A-Za-z0-9_]+/?',
        rb'api\d+\.qsvtm\.com/[A-Za-z0-9_/]{10,100}',
    ]

    h = kernel32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
    if not h:
        return []

    found = set()
    addr = 0

    while True:
        mbi = ctypes.create_string_buffer(48)
        if kernel32.VirtualQueryEx(h, ctypes.c_void_p(addr), mbi, ctypes.c_size_t(48)) == 0:
            break
        base = ctypes.c_uint64.from_buffer_copy(mbi, 0).value
        size = ctypes.c_uint64.from_buffer_copy(mbi, 24).value
        state = ctypes.c_uint32.from_buffer_copy(mbi, 32).value
        prot = ctypes.c_uint32.from_buffer_copy(mbi, 36).value

        if state == 0x1000 and 4096 < size < 200*1024*1024:
            if prot in (4, 0x20, 0x40, 0x80) or (prot & 0x100):
                try:
                    rs = min(size, 10*1024*1024)
                    buf = ctypes.create_string_buffer(rs)
                    n = ctypes.c_size_t(0)
                    if kernel32.ReadProcessMemory(h, ctypes.c_void_p(base), buf, ctypes.c_size_t(rs), ctypes.byref(n)):
                        data = buf.raw[:n.value]
                        for pat in patterns:
                            for m in re.finditer(pat, data):
                                try:
                                    txt = m.group().decode('ascii', errors='replace')
                                    txt = ''.join(c for c in txt if ord(c) >= 32)
                                    if 15 < len(txt) < 200:
                                        found.add(txt)
                                except:
                                    pass
                except:
                    pass

        addr = base + size
        if addr > 0x7FFFFFFFFFFF:
            break

    kernel32.CloseHandle(h)
    return sorted(found)


def fetch_subscription(url, name):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'clash-verge/1.0'})
        resp = urllib.request.urlopen(req, timeout=15)
        data = resp.read()

        safe_name = name.replace('/', '_').replace(':', '_')
        fpath = os.path.join(CAPTURE_DIR, f"{safe_name}.yaml")
        with open(fpath, 'wb') as f:
            f.write(data)

        text = data.decode('utf-8', errors='replace')
        proxy_count = text.count('  - {name:') + text.count('  - {')
        print(f"  [{resp.status}] {name} → {len(data):,} bytes, ~{proxy_count} proxies → {fpath}")
        return True
    except Exception as e:
        print(f"  [FAIL] {name}: {e}")
        return False


def main():
    print("=" * 60)
    print("  Falemon Subscription Extractor")
    print("=" * 60)

    for d in [os.path.expandvars(r"%APPDATA%\falemon.com"),
              os.path.expandvars(r"%LOCALAPPDATA%\falemon.com")]:
        if os.path.exists(d):
            shutil.rmtree(d, ignore_errors=True)

    print("[1] Starting Falemon...")
    falemon = start_falemon()
    pid = falemon.pid
    print(f"    PID: {pid}")

    print("[2] Waiting for account creation...")
    for i in range(25):
        time.sleep(1)
        if i % 5 == 4:
            print(f"    {i+1}s...")
        if falemon.poll() is not None:
            print(f"    Falemon exited")
            break

    print("[3] Extracting subscription tokens from memory...")
    links = scan_memory(pid)
    time.sleep(3)
    links += scan_memory(pid)

    sub_links = sorted(set(
        l for l in links
        if '/ep/' not in l and '/s3c/' not in l and 'qsvtm.com/' in l
    ))

    if not sub_links:
        print("  [!] No subscription tokens found")
        falemon.terminate()
        return

    base_url = None
    for link in sub_links:
        if not link.startswith('http'):
            link = 'https://' + link
        base_url = link.rstrip('/')
        break

    if not base_url:
        print("  [!] Cannot parse base URL")
        falemon.terminate()
        return

    print(f"\n  Token URL: {base_url}")

    print("\n[4] Fetching subscription configs...")
    fetched = 0
    for sfx in SUB_SUFFIXES:
        url = f"{base_url}/{sfx}"
        if fetch_subscription(url, sfx):
            fetched += 1

    out_path = os.path.join(CAPTURE_DIR, "subscription_links.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Token: {base_url}\n")
        f.write("=" * 40 + "\n")
        for sfx in SUB_SUFFIXES:
            f.write(f"{base_url}/{sfx}\n")

    print("\n[5] Cleanup...")
    falemon.terminate()
    time.sleep(2)
    subprocess.run(["taskkill", "/F", "/IM", "Falemon.exe"], capture_output=True)

    print(f"\n{'='*60}")
    print(f"  Done: {fetched}/{len(SUB_SUFFIXES)} configs downloaded")
    print(f"  Artifacts: {CAPTURE_DIR}")
    for f in os.listdir(CAPTURE_DIR):
        size = os.path.getsize(os.path.join(CAPTURE_DIR, f))
        print(f"    {f} ({size:,} bytes)")

    if "GITHUB_ACTIONS" in os.environ:
        for sfx in SUB_SUFFIXES:
            print(f"  [Subscription] {base_url}/{sfx}")


if __name__ == "__main__":
    main()
