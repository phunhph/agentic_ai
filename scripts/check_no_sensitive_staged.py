import re
import subprocess
import sys


BLOCKED_FILE_PATTERNS = [
    re.compile(r"(^|/)\.env($|\.)"),
    re.compile(r"(^|/)id_rsa(\.pub)?$"),
    re.compile(r"(^|/)credentials\.json$"),
    re.compile(r"(^|/)secrets?(\.|/|$)"),
]

ALLOWED_FILES = {
    ".env.example",
}

SECRET_CONTENT_PATTERNS = [
    re.compile(r"(?i)\b(api[_-]?key|secret|token|password)\b\s*[:=]\s*['\"]?[^\s'\"#]{8,}"),
    re.compile(r"-----BEGIN (RSA|EC|OPENSSH|DSA|PRIVATE) KEY-----"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
]


def run_git_command(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stderr.strip() or "Failed to run git command.")
        sys.exit(1)
    return result.stdout


def get_staged_files() -> list[str]:
    output = run_git_command(["diff", "--cached", "--name-only", "--diff-filter=ACMR"])
    files = [line.strip() for line in output.splitlines() if line.strip()]
    return files


def get_staged_content(file_path: str) -> str:
    return run_git_command(["show", f":{file_path}"])


def is_blocked_file(file_path: str) -> bool:
    normalized = file_path.replace("\\", "/")
    name = normalized.rsplit("/", maxsplit=1)[-1]
    if name in ALLOWED_FILES:
        return False
    return any(pattern.search(normalized) for pattern in BLOCKED_FILE_PATTERNS)


def has_secret_content(content: str) -> bool:
    return any(pattern.search(content) for pattern in SECRET_CONTENT_PATTERNS)


def main() -> int:
    staged_files = get_staged_files()
    blocked_files: list[str] = []
    suspicious_files: list[str] = []

    for file_path in staged_files:
        if is_blocked_file(file_path):
            blocked_files.append(file_path)
            continue

        try:
            staged_content = get_staged_content(file_path)
        except UnicodeDecodeError:
            continue

        if has_secret_content(staged_content):
            suspicious_files.append(file_path)

    if not blocked_files and not suspicious_files:
        return 0

    print("Commit blocked by security policy.\n")
    if blocked_files:
        print("Blocked sensitive file(s):")
        for path in blocked_files:
            print(f"  - {path}")
        print("")
    if suspicious_files:
        print("Potential secret detected in staged content:")
        for path in suspicious_files:
            print(f"  - {path}")
        print("")

    print("Please unstage/remove these files or sanitize values before commit.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
