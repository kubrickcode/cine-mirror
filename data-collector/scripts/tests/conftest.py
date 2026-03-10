"""테스트 환경 설정.

scripts/ 디렉토리를 sys.path에 추가하여 validate_matching 모듈을 직접 임포트할 수 있게 한다.
"""

import sys
from pathlib import Path

# scripts/ 디렉토리를 경로에 추가해 validate_matching을 최상위 모듈로 임포트
_SCRIPTS_DIR = Path(__file__).parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# 프로젝트 루트를 경로에 추가해 src 패키지를 찾을 수 있게 함
_PROJECT_ROOT = _SCRIPTS_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
