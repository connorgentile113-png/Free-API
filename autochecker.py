import re
import requests
import json
import sys
import os
import subprocess
import base64
import time

# Standard libraries for terminal manipulation
try:
    import tty
    import termios
except ImportError:
    # Fallback for non-Unix systems if needed, though session context says Linux
    tty = None
    termios = None

BASE_URL = "https://aiapiv2.pekpik.com/v1"
README_URL = "https://raw.githubusercontent.com/alistaitsacle/free-llm-api-keys/main/README.md"

def fetch_readme():
    print(f"[*] Fetching latest README from {README_URL}...")
    response = requests.get(README_URL)
    response.raise_for_status()
    return response.text

def extract_keys_and_models(content):
    print("[*] Extracting keys and metadata...")
    pattern = r"\| `(sk-[a-zA-Z0-9]+)` \| ([a-zA-Z0-9.-]+) \| [^|]+ \| ([^|]+) \| ([^|]+) \|"
    matches = re.findall(pattern, content)
    
    unique_entries = []
    seen = set()
    for key, model, budget, rpm in matches:
        if key not in seen:
            unique_entries.append({
                "key": key, 
                "model": model,
                "budget": budget.strip(),
                "rpm": rpm.strip()
            })
            seen.add(key)
    return unique_entries

def check_key(key, model):
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1}
    try:
        response = requests.post(f"{BASE_URL}/chat/completions", headers=headers, data=json.dumps(payload), timeout=7)
        return response.status_code == 200, response
    except Exception as e:
        return False, str(e)

def copy_to_clipboard(text):
    """Cross-platform clipboard helper with OSC 52 terminal fallback."""
    # 1. Try system utilities first
    try:
        if sys.platform == 'darwin':
            subprocess.run(['pbcopy'], input=text.encode('utf-8'), check=True)
            return True
        elif sys.platform == 'linux':
            # Try xclip then xsel
            try:
                subprocess.run(['xclip', '-selection', 'clipboard'], input=text.encode('utf-8'), check=True, stderr=subprocess.DEVNULL)
                return True
            except:
                try:
                    subprocess.run(['xsel', '--clipboard', '--input'], input=text.encode('utf-8'), check=True, stderr=subprocess.DEVNULL)
                    return True
                except:
                    pass
        elif sys.platform == 'win32' or os.name == 'nt':
            subprocess.run(['clip'], input=text.encode('utf-16'), check=True, shell=True)
            return True
    except:
        pass

    # 2. OSC 52 Escape Sequence Fallback (Works in modern terminals like Mint's GNOME Terminal, Alacritty, iTerm2)
    try:
        b64_text = base64.b64encode(text.encode('utf-8')).decode('utf-8')
        osc52_sequence = f"\033]52;c;{b64_text}\a"
        sys.stdout.write(osc52_sequence)
        sys.stdout.flush()
        return True
    except:
        return False

def get_key_press():
    """Reads a single key press from the terminal."""
    if not tty or not termios:
        return sys.stdin.read(1)
    
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
        if ch == '\x1b': # Escape sequence
            ch += sys.stdin.read(2)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

def interactive_menu(working_keys):
    if not working_keys:
        return

    current_idx = 0
    while True:
        # Clear screen and move cursor to top
        sys.stdout.write("\033[H\033[J")
        print("="*60)
        print("🚀 WORKING KEYS FOUND! Use ARROW KEYS to select, ENTER to copy.")
        print("="*60 + "\n")

        for i, k in enumerate(working_keys):
            prefix = " > " if i == current_idx else "   "
            line = f"{prefix} {k['model']:<20} | {k['budget']:<8} | {k['rpm']:<8} | {k['key'][:20]}..."
            if i == current_idx:
                # Highlight the selected line (Cyan background)
                print(f"\033[46m\033[30m{line}\033[0m")
            else:
                print(line)

        print("\n" + "-"*60)
        print(" [ ↑ / ↓ ] Navigate | [ ENTER ] Copy Key | [ Q ] Quit")
        
        key = get_key_press()
        if key == '\x1b[A': # Up
            current_idx = (current_idx - 1) % len(working_keys)
        elif key == '\x1b[B': # Down
            current_idx = (current_idx + 1) % len(working_keys)
        elif key == '\r' or key == '\n': # Enter
            selected_key = working_keys[current_idx]['key']
            if copy_to_clipboard(selected_key):
                print(f"\n✅ Attempted to copy to clipboard: {selected_key}")
                print("(Note: If it didn't copy, your terminal might not support OSC 52)")
                sys.exit(0)
            else:
                print(f"\n❌ Failed to copy to clipboard. Please copy manually:")
                print(f"   {selected_key}")
                sys.exit(0)
        elif key.lower() == 'q':
            sys.exit(0)

def main():
    try:
        content = fetch_readme()
        entries = extract_keys_and_models(content)
        
        if not entries:
            print("[!] No keys found in README.")
            return

        print(f"[*] Found {len(entries)} unique keys. Starting check...\n")
        print(f"{'Key':<50} | {'Model':<20} | {'Budget':<8} | {'RPM'}")
        print("-" * 110)

        working_keys = []
        for entry in entries:
            is_working, response = check_key(entry["key"], entry["model"])
            status = "✅ WORKING" if is_working else "❌ FAILED"
            print(f"{entry['key']:<50} | {entry['model']:<20} | {entry['budget']:<8} | {entry['rpm']:<8} | {status}")
            if is_working:
                working_keys.append(entry)

        if working_keys:
            # Short delay to show results before jumping into interactive menu
            print("\n[*] Starting interactive selection...")
            time.sleep(1)
            interactive_menu(working_keys)
        else:
            print("\n[!] No working keys found.")

    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f"[!] Error: {e}")

if __name__ == "__main__":
    main()
