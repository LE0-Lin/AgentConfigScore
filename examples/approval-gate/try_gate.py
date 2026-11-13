"""Try the operator console with a disposable file; no existing user files accepted."""
from pathlib import Path
from tempfile import TemporaryDirectory

from gate import create_session


def main():
    with TemporaryDirectory(prefix="acs-approval-console-") as directory:
        root = Path(directory).resolve()
        target = root / "obsolete.txt"
        target.write_text("Disposable demonstration file.\n", encoding="utf-8")
        operator, delete = create_session(root)
        request = {"tool": "delete_file", "path": "obsolete.txt"}
        result = delete(request)
        assert result["decision"] == "denied" and target.is_file()
        print("Agent request: delete_file obsolete.txt")
        print("Without approval:", result["reason"], "(file still exists)")
        print("Operator review: obsolete.txt contains", repr(target.read_text(encoding="utf-8")))
        print("Only this freshly created temporary file can be selected by this console.")
        try:
            answer = input("Type DELETE to authorize this one deletion; anything else refuses: ")
        except (EOFError, KeyboardInterrupt):
            answer = ""
        if answer != "DELETE":
            print("Operator refused. No delete_file operation was performed.")
        else:
            token = operator.approve("obsolete.txt")
            result = delete({**request, "approval": token})
            if result["decision"] != "executed" or target.exists():
                print("Deletion did not complete; no success is claimed.")
                return 2
            print("Approved operation executed. Verified: temporary target no longer exists.")
        print("Disposable workspace cleanup follows, independent of the tool decision.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
