import ctypes
import ctypes.wintypes as wintypes
import re
import subprocess
import base64
import json
import os

kernel32 = ctypes.windll.kernel32
OpenProcess = kernel32.OpenProcess
OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
OpenProcess.restype = wintypes.HANDLE

ReadProcessMemory = kernel32.ReadProcessMemory
ReadProcessMemory.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.LPVOID, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
ReadProcessMemory.restype = wintypes.BOOL

CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [wintypes.HANDLE]
CloseHandle.restype = wintypes.BOOL

VirtualQueryEx = kernel32.VirtualQueryEx
VirtualQueryEx.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.LPVOID, ctypes.c_size_t]
VirtualQueryEx.restype = ctypes.c_size_t

class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", wintypes.DWORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD),
        ("Type", wintypes.DWORD),
    ]

MEM_COMMIT = 0x1000
PAGE_READABLE = [0x02, 0x04, 0x08, 0x20, 0x40]

def get_workbuddy_pids():
    result = subprocess.run(['tasklist', '/FO', 'CSV'], capture_output=True, text=True)
    pids = []
    for line in result.stdout.strip().split('\n')[1:]:
        parts = line.split('","')
        if len(parts) >= 2 and 'workbuddy' in parts[0].lower():
            try:
                pids.append(int(parts[1].strip().replace('"', '')))
            except ValueError:
                pass
    return pids

def find_all_memory_blocks(pid, max_regions=800):
    h_process = OpenProcess(0x0010 | 0x0400, False, pid)
    if not h_process:
        return []
    blocks = []
    try:
        address = 0x10000
        mbi = MEMORY_BASIC_INFORMATION()
        mbi_size = ctypes.sizeof(mbi)
        region_count = 0
        while VirtualQueryEx(h_process, ctypes.c_void_p(address), ctypes.byref(mbi), mbi_size) and region_count < max_regions:
            if mbi.State == MEM_COMMIT and mbi.Protect in PAGE_READABLE and mbi.BaseAddress is not None and mbi.RegionSize > 0:
                region_size = min(mbi.RegionSize, 10 * 1024 * 1024)
                buffer = ctypes.create_string_buffer(region_size)
                bytes_read = ctypes.c_size_t(0)
                if ReadProcessMemory(h_process, ctypes.c_void_p(mbi.BaseAddress), buffer, region_size, ctypes.byref(bytes_read)):
                    blocks.append((mbi.BaseAddress, buffer.raw[:bytes_read.value]))
                region_count += 1
            next_addr = (mbi.BaseAddress or 0) + (mbi.RegionSize or 0)
            if next_addr <= address or next_addr > 0x7FFF00000000:
                break
            address = next_addr
    finally:
        CloseHandle(h_process)
    return blocks

def extract_context(data, offset, radius=300):
    start = max(0, offset - radius)
    end = min(len(data), offset + radius)
    try:
        return data[start:end].decode('utf-8', errors='ignore')
    except:
        return data[start:end].decode('latin-1', errors='ignore')

def decode_jwt_payload(token):
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + '=' * (4 - len(parts[1]) % 4)))
        return payload
    except Exception:
        return None

def scan_for_tokens(pid):
    jwt_pattern = re.compile(rb'eyJ[A-Za-z0-9_-]{20,}\.eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}')
    blocks = find_all_memory_blocks(pid, max_regions=800)
    tokens = []
    for base_addr, data in blocks:
        for m in jwt_pattern.finditer(data):
            token = m.group(0).decode('ascii')
            if len(token) < 100:
                continue
            payload = decode_jwt_payload(token)
            if not payload:
                continue
            tokens.append({
                'token': token,
                'payload': payload,
                'offset': m.start(),
                'context': extract_context(data, m.start(), 400)
            })
    return tokens

def scan_for_refresh_tokens(pid):
    blocks = find_all_memory_blocks(pid, max_regions=600)
    results = []
    refresh_pattern = re.compile(rb'refreshToken["\']?\s*[:=]\s*["\']?([A-Za-z0-9_\-\.]{50,})')
    for base_addr, data in blocks:
        for m in refresh_pattern.finditer(data):
            token = m.group(1).decode('ascii')
            context = extract_context(data, m.start(), 300)
            results.append({'token': token, 'context': context[:200]})
    return results

def main():
    print("扫描 WorkBuddy 进程内存中的 token...")
    pids = get_workbuddy_pids()
    if not pids:
        print("未找到 WorkBuddy 进程")
        return

    all_tokens = []
    all_refresh = []
    for pid in pids:
        all_tokens.extend(scan_for_tokens(pid))
        all_refresh.extend(scan_for_refresh_tokens(pid))

    seen = set()
    unique_tokens = []
    for t in all_tokens:
        if t['token'] not in seen:
            seen.add(t['token'])
            unique_tokens.append(t)

    print(f"\n找到 {len(unique_tokens)} 个唯一 JWT token:\n")
    saved = False
    for i, t in enumerate(unique_tokens, 1):
        payload = t['payload']
        print(f"--- Token {i} ---")
        print(f"Type: {payload.get('typ', 'Unknown')}")
        print(f"Sub:  {payload.get('sub', 'N/A')}")
        print(f"Azp:  {payload.get('azp', 'N/A')}")
        print(f"Exp:  {payload.get('exp', 'N/A')}")
        print(f"Iss:  {payload.get('iss', 'N/A')}")
        print(f"Token (前100字符): {t['token'][:100]}...")
        print()
        if not saved and payload.get('typ') == 'Bearer' and payload.get('sub'):
            auth_data = {
                'token': t['token'],
                'uid': payload.get('sub'),
                'nickname': payload.get('nickname', ''),
                'exp': payload.get('exp')
            }
            save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'auth.json')
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(auth_data, f, ensure_ascii=False, indent=2)
            print(f"[已保存] Token 和 UID 已写入: {save_path}")
            saved = True

    if not saved:
        print("[警告] 未找到有效的 Bearer token，未保存 auth.json")

    if all_refresh:
        print(f"\n找到 {len(all_refresh)} 个 refreshToken:")
        for i, r in enumerate(all_refresh[:5], 1):
            print(f"--- Refresh Token {i} ---")
            print(f"Value: {r['token'][:100]}...")
            print(f"Context: {r['context'][:200]}")
            print()
    else:
        print("未找到 refreshToken")

if __name__ == "__main__":
    main()
