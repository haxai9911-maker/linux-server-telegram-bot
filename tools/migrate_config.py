#!/usr/bin/env python3
"""One-time migration tool: convert existing .txt/.env config files to config.yaml.

Searches ONLY the current directory for old linux_bot/ and linux_monitoring/ directories,
reads the .txt config files, and generates a modern config.yaml in the current directory.
"""

from __future__ import annotations

import glob
import os
import sys

import yaml

# ============================================================
# التغيير الأول: البحث فقط في المجلد الحالي (وليس كل الخادم)
# ============================================================
def _find_legacy_dirs() -> tuple[str | None, str | None]:
    """Search ONLY the current directory for old linux_bot/ and linux_monitoring/ directories."""
    bot_dir = None
    mon_dir = None
    current_dir = os.getcwd()

    print(f"Searching for old linux_bot/ and linux_monitoring/ in: {current_dir}")

    # نبحث فقط في المجلد الحالي، وليس في ~ و /opt و /home ...
    base_paths = [current_dir]

    for base in base_paths:
        if not os.path.isdir(base):
            continue
        # نبحث في المجلد الحالي ومجلد فرعي واحد فقط (بدلاً من 3 مستويات)
        for pattern in [
            os.path.join(base, "linux_bot"),
            os.path.join(base, "*", "linux_bot"),
        ]:
            for match in glob.glob(pattern):
                if os.path.isdir(match) and os.path.exists(os.path.join(match, "main.py")):
                    if bot_dir is None:
                        bot_dir = match
                        print(f"  Found linux_bot: {match}")

        for pattern in [
            os.path.join(base, "linux_monitoring"),
            os.path.join(base, "*", "linux_monitoring"),
        ]:
            for match in glob.glob(pattern):
                if os.path.isdir(match) and os.path.exists(os.path.join(match, "main.py")):
                    if mon_dir is None:
                        mon_dir = match
                        print(f"  Found linux_monitoring: {match}")

        if bot_dir and mon_dir:
            break

    if not bot_dir and not mon_dir:
        print("  No legacy directories found in the current directory.")
    return bot_dir, mon_dir


def _read_txt(path: str) -> list[str]:
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


def _parse_servers(lines: list[str]) -> list[dict]:
    servers = []
    for line in lines:
        if "=" not in line:
            continue
        name, _, addr = line.partition("=")
        host, _, port = addr.partition(":")
        servers.append(
            {
                "name": name.strip(),
                "host": host.strip(),
                "port": int(port.strip()) if port.strip() else 443,
            }
        )
    return servers


def main():
    # ============================================================
    # التغيير الثاني: استخدم المجلد الحالي (وليس جذر المشروع)
    # ============================================================
    base = os.getcwd()  # <--- هنا التغيير الأهم

    # ============================================================
    # التغيير الثالث: ابحث عن المجلدات القديمة في الحالي فقط
    # ============================================================
    bot_dir, mon_dir = _find_legacy_dirs()

    # إذا لم يجدها في المجلد الحالي، لا نذهب للجذر، بل نخرج مباشرة
    if bot_dir is None and mon_dir is None:
        print("\nERROR: Could not find linux_bot/ or linux_monitoring/ in the current directory.")
        print(f"Please make sure these folders exist in: {base}")
        print("And that each contains a 'main.py' file.")
        sys.exit(1)

    # نضع قيمة افتراضية للمجلدات إذا كانت None (لكنها لن تكون None لأننا خرجنا أعلاه)
    if bot_dir is None:
        bot_dir = os.path.join(base, "linux_bot")
    if mon_dir is None:
        mon_dir = os.path.join(base, "linux_monitoring")

    # ============================================================
    # التغيير الرابع: ابحث عن .env في المجلد الحالي فقط
    # ============================================================
    env_vars = {}
    env_path = os.path.join(base, ".env")  # فقط في الحالي
    if os.path.exists(env_path):
        print(f"Reading .env from: {env_path}")
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    env_vars[key.strip()] = val.strip()
    else:
        print("No .env file found in current directory (skipping).")

    # ============================================================
    # باقي الكود كما هو (قراءة الملفات وتحليلها وبناء الـ YAML)
    # ============================================================
    bot_services = _read_txt(os.path.join(bot_dir, "bot_services.txt"))
    bot_logfiles = _read_txt(os.path.join(bot_dir, "bot_logfiles.txt"))
    bot_servers_raw = _read_txt(os.path.join(bot_dir, "bot_servers.txt"))
    mon_services = _read_txt(os.path.join(mon_dir, "monitoring_services.txt"))
    mon_containers = _read_txt(os.path.join(mon_dir, "monitoring_containers.txt"))
    mon_servers_raw = _read_txt(os.path.join(mon_dir, "monitoring_servers.txt"))

    found = sum(
        1 for lst in [bot_services, bot_logfiles, bot_servers_raw, mon_services, mon_containers, mon_servers_raw] if lst
    )
    if found == 0:
        print("\nNo .txt config files found inside the linux_bot/ or linux_monitoring/ folders.")
        print("Nothing to migrate.")
        sys.exit(1)

    print(f"\nFound {found} config file(s) to migrate.")

    bot_servers = _parse_servers(bot_servers_raw)
    mon_servers = _parse_servers(mon_servers_raw)

    config = {
        "telegram": {
            "bot_token": "${SECRET_TOKEN}",
            "allowed_users": ["${CHAT_ID_PERSON1}"],
        },
        "wol": {
            "address": "${WOL_ADDRESS}",
            "hostname": "${WOL_HOSTNAME}",
            "interface": "eth0",
        },
        "features": {
            "systemd_services": True,
            "docker_containers": True,
            "docker_compose": True,
            "custom_commands": True,
            "wol": True,
            "security_overview": True,
            "backups": True,
            "container_updates": True,
            "logs": True,
            "server_ping": True,
            "system_info": True,
            "stress_test": True,
            "fan_control": True,
            "reboot": True,
        },
        "services": bot_services,
        "compose_stacks": [],
        "servers": bot_servers,
        "logfiles": bot_logfiles,
        "scripts": {
            "update_containers": "",
            "backup": "",
        },
        "server_states_path": "server_states.json",
        "log_directory": "./logs",
        "monitoring": {
            "interval_minutes": 5,
            "containers": mon_containers,
            "servers": mon_servers,
            "services": mon_services,
            "thresholds": {
                "cpu_percent": 80,
                "storage_percent": 90,
                "temperature_celsius": 50,
            },
            "security": {
                "check_fail2ban": True,
                "check_ufw": True,
                "check_ssh_sessions": True,
            },
        },
    }

    # ============================================================
    # التغيير الخامس: اكتب config.yaml في المجلد الحالي (وليس الجذر)
    # ============================================================
    output = os.path.join(base, "config.yaml")
    if os.path.exists(output):
        print(f"\n{output} already exists!")
        answer = input("Overwrite? [y/N] ").strip().lower()
        if answer != "y":
            print("Aborted.")
            sys.exit(0)

    with open(output, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    print(f"\nConfig written to {output}")
    print("Review the file and adjust values as needed.")
    print("Remember to keep your .env file for SECRET_TOKEN, CHAT_ID, and WOL variables.")


if __name__ == "__main__":
    main()