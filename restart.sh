#!/bin/bash

# ----------------- 설정 -----------------
# 1. 파이썬 애플리케이션이 위치한 절대 경로를 입력하세요.
APP_DIR="/path/to/your/app"

# 2. 찾고자 하는 프로세스 패턴을 입력하세요.
PROCESS_PATTERN="python3 app.py"

# 3. 재시작 시 실행할 전체 명령어를 입력하세요.
START_COMMAND="authbind --deep nohup python3 app.py &"
# ----------------------------------------

echo "============================================="
echo "Application Restart Script"
echo "Target: $PROCESS_PATTERN"
echo "Location: $APP_DIR"
echo "============================================="

# 1. 애플리케이션 디렉토리로 이동
# nohup.out 파일 생성 및 app.py 실행을 위해 필수입니다.
cd "$APP_DIR" || { echo "Error: 디렉토리를 찾을 수 없습니다: $APP_DIR"; exit 1; }

# 2. 프로세스 찾기 및 종료
# pkill -f 옵션으로 커맨드 라인 전체에서 패턴을 찾아 해당 프로세스를 종료합니다.
echo "--> 현재 실행 중인 프로세스를 찾아서 종료합니다..."
if pkill -9 -f "$PROCESS_PATTERN"; then
    echo "--> 프로세스가 성공적으로 종료되었습니다."
    sleep 2 # 프로세스가 완전히 종료될 시간을 줍니다.
else
    echo "--> 실행 중인 프로세스가 없거나, 종료할 수 없습니다."
fi

# 3. 프로세스 재시작
echo "--> 애플리케이션을 재시작합니다..."
eval $START_COMMAND

# 4. 재시작 확인
sleep 2 # 프로세스가 시작될 시간을 줍니다.
echo "--> 재시작 확인 중..."
if pgrep -f "$PROCESS_PATTERN" > /dev/null; then
    NEW_PID=$(pgrep -f "$PROCESS_PATTERN")
    echo "✅ 성공: 애플리케이션이 새로운 PID($NEW_PID)로 실행되었습니다."
else
    echo "❌ 실패: 애플리케이션 재시작에 실패했습니다. nohup.out 파일을 확인하세요."
fi

echo "스크립트 실행 완료."