import RPi.GPIO as GPIO
import time
import random
import threading
from flask import Flask, render_template, request, redirect, url_for
import os
import json

# Flask 앱 초기화
app = Flask(__name__)
LEADERBOARD_FILE = "leaderboard.json"
leaderboard = []

game_state = {
    "username": None,
    "restart": False,
    "take_photo": False
}

# 핀 정의
KEYPAD_PINS = [6, 12, 13, 16, 19, 20, 26, 21]  # Keypad PB4 ~ PB1, PB8 ~ PB5 GPIO 핀
LED_PINS = [4, 17, 18, 27, 22, 23, 24, 25]     # LED1 ~ LED8 GPIO 핀

KEYPAD_TO_LED_MAP = {
    4: 1, 3: 2, 2: 3, 1: 4, 8: 5, 7: 6, 6: 7, 5: 8
}

LED_ON = GPIO.HIGH
LED_OFF = GPIO.LOW
MAX_ROUNDS = 99  # 최대 라운드 수

def setup_pins():
    """GPIO 핀 설정"""
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    for pin in LED_PINS:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, LED_OFF)
    for pin in KEYPAD_PINS:
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def display_pattern(pattern):
    """LED 패턴 표시"""
    for pb in pattern:
        led_num = KEYPAD_TO_LED_MAP[pb]
        GPIO.output(LED_PINS[led_num - 1], LED_ON)
        time.sleep(0.5)
        GPIO.output(LED_PINS[led_num - 1], LED_OFF)
        time.sleep(0.2)

def read_user_input(expected_length):
    """사용자 입력 읽기"""
    user_input = []
    while len(user_input) < expected_length:
        for pb_num, led_num in KEYPAD_TO_LED_MAP.items():
            if not GPIO.input(KEYPAD_PINS[pb_num - 1]):
                user_input.append(pb_num)
                GPIO.output(LED_PINS[led_num - 1], LED_ON)
                time.sleep(0.5)
                GPIO.output(LED_PINS[led_num - 1], LED_OFF)
                while not GPIO.input(KEYPAD_PINS[pb_num - 1]):
                    time.sleep(0.1)
    return user_input

def flash_leds(times, duration=0.5):
    """모든 LED를 번쩍이는 효과"""
    for _ in range(times):
        for pin in LED_PINS:
            GPIO.output(pin, LED_ON)
        time.sleep(duration)
        for pin in LED_PINS:
            GPIO.output(pin, LED_OFF)
        time.sleep(duration)

def capture_photo(username, score):
    """사진 촬영"""
    filename = f"static/photos/{username}_{score}.jpg"
    try:
        import picamera
        with picamera.PiCamera() as camera:
            camera.resolution = (640, 480)  # 해상도 설정
            camera.start_preview()
            time.sleep(2)
            camera.capture(filename)
            camera.stop_preview()
    except ImportError:
        print("Camera module not available.")
    return filename

def save_result(username, score, photo_path=None):
    """점수 및 사진 저장"""
    leaderboard.append({'username': username, 'score': score, 'photo': photo_path or "No Photo"})
    leaderboard.sort(key=lambda x: x['score'], reverse=True)
    save_leaderboard()

def save_leaderboard():
    """점수판 저장"""
    with open(LEADERBOARD_FILE, "w") as f:
        json.dump(leaderboard, f)

def load_leaderboard():
    """점수판 로드"""
    if os.path.exists(LEADERBOARD_FILE):
        with open(LEADERBOARD_FILE, "r") as f:
            return json.load(f)
    return []

@app.route('/', methods=['GET', 'POST'])
def leaderboard_page():
    """리더보드 페이지"""
    if request.method == 'POST':
        # 사용자 입력 처리
        game_state['username'] = request.form.get('username')
        game_state['restart'] = request.form.get('restart') == 'yes'
        game_state['take_photo'] = request.form.get('take_photo') == 'yes'
        return redirect(url_for('leaderboard_page'))

    return render_template('leaderboard.html', leaderboard=leaderboard, game_state=game_state)

def run_server():
    """Flask 서버 실행"""
    app.run(host='0.0.0.0', port=3555, debug=False)

def main():
    """메인 게임 루프"""
    global leaderboard
    leaderboard = load_leaderboard()

    # GPIO 핀 초기화
    setup_pins()

    try:
        while True:
            username = game_state['username']
            if not username:
                print("No username provided. Waiting for input from the web interface...")
                time.sleep(1)
                continue  # 이름 입력 대기

            score = 0
            for round_num in range(1, MAX_ROUNDS + 1):
                score = round_num
                time.sleep(1)

                # 새로운 랜덤 패턴 생성
                new_pattern = [random.choice(list(KEYPAD_TO_LED_MAP.keys())) for _ in range(round_num)]
                display_pattern(new_pattern)

                # 사용자 입력 확인
                user_input = read_user_input(len(new_pattern))
                if user_input != new_pattern:
                    print(f"Game Over! Final score: {score}")
                    # 모든 LED 3초 동안 켜기
                    for pin in LED_PINS:
                        GPIO.output(pin, LED_ON)
                    time.sleep(3)
                    for pin in LED_PINS:
                        GPIO.output(pin, LED_OFF)

                    # 사진 촬영 여부 확인
                    photo_path = None
                    if game_state['take_photo']:
                        photo_path = capture_photo(username, score)
                    save_result(username, score, photo_path)
                    break  # 현재 게임 루프 종료 후 재시작

            # 게임 상태 초기화 및 재시작
            game_state['username'] = None
            print("Restarting game...")

    except KeyboardInterrupt:
        print("Program terminated by user.")
    finally:
        GPIO.cleanup()  # GPIO 초기화



if __name__ == "__main__":
    # Flask 서버를 백그라운드에서 실행
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # 게임 루프 실행
    main()
