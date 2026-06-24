import json
import re
import sys


def main():
    try:
        input_data = sys.stdin.read()
        if not input_data.strip():
            sys.exit(0)

        data = json.loads(input_data)
        tool_name = data.get("tool_name")
        tool_input = data.get("tool_input", {})

        # Check if the tool is run_command
        if tool_name == "run_command":
            command = tool_input.get("CommandLine", "") or tool_input.get("command", "")

            # Match destructive commands like rm -rf /
            # e.g., rm -rf /, rm -fr /, rm -r -f /
            destructive_pattern = r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+/"
            if re.search(destructive_pattern, command) or "rm -rf /" in command:
                sys.stderr.write(
                    f"Security Policy Violation: Command contains blocked destructive operation: {command}\n"
                )
                sys.exit(2)

    except Exception as e:
        sys.stderr.write(f"Error in validate_tool_call hook: {e}\n")
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
