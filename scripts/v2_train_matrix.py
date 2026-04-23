import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from v2.learn import train_matrix_v2


def main() -> None:
    artifact = train_matrix_v2()
    print(artifact)


if __name__ == "__main__":
    main()
