"""Entry point for code-logger CLI."""
from code_logger_cli.commands import main
if __name__ == "__main__":
    exit(main() or 0)
