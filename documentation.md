# Barrier-Free Kiosk 상세 동작 설명

이 문서는 Barrier-Free Kiosk 애플리케이션의 주요 기능별 동작 원리를 상세히 설명합니다.
각 기능은 Flask 라우트, 서비스 로직, 그리고 필요한 경우 JavaScript를 사용한 프론트엔드 상호작용으로 구성됩니다.

## 목차

1. [공통 설정 및 초기화](#공통-설정-및-초기화)
2. [홈 화면 (`home.py`, `home.html`)](#홈-화면)
3. [접수 (`reception.py`, `reception.html`, `reception_service.py`)](#접수-기능)
4. [수납 (`payment.py`, `payment.html`, `payment_service.py`)](#수납-기능)
5. [증명서 발급 (`certificate.py`, `certificate.html`, `certificate_service.py`)](#증명서-발급-기능)
6. [AI 챗봇 (`chatbot.py`, `chatbot_interface.html`, `chatbot_service.py`)](#ai-챗봇-기능)
7. [JavaScript 상호작용 (`script.js`)](#javascript-상호작용)

---

## 1. 공통 설정 및 초기화

### Flask 애플리케이션 초기화 (`app/__init__.py`)
- Flask 앱 인스턴스 생성
- 블루프린트 등록 (home, reception, payment, certificate, chatbot)
- 국제화 (i18n) 설정: `flask_babel`을 사용하여 한국어/영어 지원
- 요청 시 언어 선택 로직 (`get_locale` 함수)

### 기본 템플릿 (`templates/base.html`)
- 모든 페이지의 기본 구조 제공
- 헤더: 언어 변경 버튼, 글자 크기 조절 버튼
- CSS 및 JavaScript 파일 링크
- 콘텐츠 블록 (`{% block content %}`)

---

## 2. 홈 화면

### 라우트 (`app/routes/home.py`)
- **`@home_bp.route('/')`**:
    - 기능: 애플리케이션의 메인 페이지를 렌더링합니다.
    - HTTP 메소드: GET
    - 동작:
        1. `templates/home.html` 템플릿을 렌더링합니다.
        2. 초기 환영 음성 안내 (`audio_url`)를 템플릿에 전달합니다.

### 템플릿 (`templates/home.html`)
- 주요 기능으로 이동하는 버튼 표시: 접수, 수납, 증명서 발급, AI 챗봇.
- 로고 이미지 표시 (현재 `CAU-health-icon.webp`).
- 환영 음성 자동 재생 기능 (JavaScript를 통해 제어될 수 있음).

---
## 3. 접수 기능

### 라우트 (`app/routes/reception.py`)

- **`@reception_bp.route('/', methods=['GET', 'POST'])` - `reception()`**:
    - 기능: 접수 초기 화면을 표시하고, 접수 방법(주민번호 스캔/직접 입력) 선택을 처리합니다.
    - GET: `templates/reception.html`을 `STEP_SCAN_OPTIONS` 상태로 렌더링합니다.
    - POST:
        - `scan_option` 값에 따라 다음 단계로 진행합니다.
        - 'RRN_SCAN': 주민번호 스캔 단계로 (구현 예정 알림).
        - 'MANUAL_INPUT': 주민번호 수동 입력 단계로 (`STEP_MANUAL_RRN_INPUT`).
        - 'FOREIGNER_SCAN': 외국인 등록번호 스캔 단계로 (구현 예정 알림).
    - 세션에 `reception_step`을 저장하여 현재 단계를 추적합니다.

- **`@reception_bp.route('/manual_rrn', methods=['POST'])` - `manual_rrn_input()`**:
    - 기능: 수동으로 입력된 주민등록번호를 검증하고 다음 단계로 안내합니다.
    - POST:
        1. 폼에서 주민등록번호 앞자리(`rrn_front`)와 뒷자리(`rrn_back`)를 가져옵니다.
        2. `reception_service.validate_rrn`을 호출하여 주민번호 유효성을 검사합니다.
        3. 유효하면, `reception_service.check_existing_reservation`을 통해 기존 예약 정보를 확인합니다.
            - 기존 예약이 있고 완료되지 않았다면, 해당 예약 정보를 세션에 저장하고 증상 선택 단계(`STEP_SYMPTOM_INPUT`)로 이동합니다.
            - 유효한 주민번호이지만 예약 정보가 없다면, 사용자 정보를 세션에 저장하고 증상 선택 단계(`STEP_SYMPTOM_INPUT`)로 이동합니다.
        4. 유효하지 않으면, 오류 메시지와 함께 `STEP_MANUAL_RRN_INPUT` 상태로 `reception.html`을 다시 렌더링합니다.

- **`@reception_bp.route('/symptoms', methods=['POST'])` - `symptom_input()`**:
    - 기능: 선택된 증상을 처리하고 접수를 완료합니다.
    - POST:
        1. 폼에서 선택된 증상(`symptoms`)을 가져옵니다.
        2. `reception_service.complete_reception`을 호출하여 접수를 완료하고 대기번호를 발급받습니다.
            - 이 서비스 함수는 `data/reservations.csv`에 예약 정보를 저장/업데이트합니다.
        3. 성공적으로 접수되면, 접수 완료 및 대기번호 안내 단계(`STEP_COMPLETED`)로 이동하여 `reception.html`을 렌더링합니다.
        4. 오류 발생 시, 오류 메시지와 함께 `STEP_SYMPTOM_INPUT` 상태로 다시 렌더링합니다.

- **`@reception_bp.route('/reset_session', methods=['GET'])` - `reset_session()`**:
    - 기능: 접수 과정 중 세션 정보를 초기화하고 첫 화면으로 돌아갑니다.
    - GET: 세션에서 `reservation_info`, `reception_step`, `patient_info`를 삭제하고 홈 화면으로 리다이렉트합니다.

### 서비스 (`app/services/reception_service.py`)

- **`validate_rrn(rrn_front, rrn_back)`**:
    - 주민등록번호의 유효성을 검사합니다 (형식, 체크섬 등).
    - 유효하면 True, 아니면 False 반환.

- **`check_existing_reservation(rrn)`**:
    - `data/reservations.csv` 파일을 읽어 해당 주민번호로 진행 중인 예약이 있는지 확인합니다.
    - 있다면 예약 정보(딕셔너리) 반환, 없다면 None 반환.

- **`initiate_reservation(patient_info)`**:
    - 새로운 예약 정보를 초기화합니다. (주민번호, 이름, 초기 상태 등)
    - `data/reservations.csv`에 새 예약을 추가하거나 기존 예약이 없다면 생성합니다.
    - 생성된 예약 정보 반환. (이 함수는 현재 라우트에서 직접 호출되지 않고, `complete_reception` 등에서 내부적으로 사용될 수 있음)

- **`complete_reception(patient_info, symptoms)`**:
    - 환자 정보와 증상을 바탕으로 접수를 완료합니다.
    - `data/reservations.csv`에서 해당 환자 정보를 찾아 증상, 접수 완료 시간, 대기번호를 업데이트하거나 새로 기록합니다.
    - 성공 시 대기번호를 포함한 예약 정보 반환, 실패 시 None 반환.

- **`get_next_ticket_number()`**:
    - `data/reservations.csv`를 참조하여 다음 대기번호를 생성합니다.

### 템플릿 (`templates/reception.html`)
- `reception_step` 값에 따라 다른 UI를 동적으로 표시합니다:
    - `STEP_SCAN_OPTIONS`: 접수 방법 선택 (스캔/수동입력).
    - `STEP_MANUAL_RRN_INPUT`: 주민번호 수동 입력 폼.
    - `STEP_SYMPTOM_INPUT`: 증상 선택 폼.
    - `STEP_COMPLETED`: 접수 완료 메시지 및 대기번호 표시.
- 오류 메시지 표시 영역.
- '처음으로' 버튼 (세션 초기화).

---
## 4. 수납 기능

### 라우트 (`app/routes/payment.py`)

- **`@payment_bp.route('/', methods=['GET', 'POST'])` - `payment()`**:
    - 기능: 수납 절차를 관리합니다. 환자 정보 및 예약된 진료과를 확인하고, 처방 불러오기 요청을 처리하거나 실제 결제를 진행합니다.
    - GET:
        1. 세션에서 환자 주민번호(`patient_rrn`)와 이름(`patient_name`)을 가져옵니다. 정보가 없으면 접수 페이지로 리다이렉트합니다.
        2. `reception_service.lookup_reservation`을 호출하여 환자의 예약 정보를 조회합니다. 예약 정보가 없거나 진료과(`department`) 정보가 없으면 접수 페이지로 리다이렉트합니다.
        3. `payment.html`을 `initial_payment` 단계로 렌더링하며, 진료과 정보를 전달합니다. (JavaScript에서 이 정보를 사용하여 처방을 로드합니다.)
    - POST:
        1. 폼에서 결제 금액(`amount`)과 방법(`method`)을 가져옵니다. 환자 ID는 세션의 `patient_rrn`을 사용합니다.
        2. `payment_service.process_new_payment`를 호출하여 결제를 처리하고 고유한 `pay_id`를 받습니다.
        3. 세션에 저장된 `last_prescriptions` (처방명 리스트)와 `last_total_fee` (총액)를 가져옵니다.
        4. `payment_service.update_reservation_with_payment_details`를 호출하여 `reservations.csv` 파일에 해당 환자의 처방 내역, 총액, 그리고 상태를 'Paid'로 업데이트합니다.
        5. 결제 완료 화면 (`payment.done`)으로 리다이렉트하며 `pay_id`를 전달합니다.

- **`@payment_bp.route('/load_prescriptions', methods=['GET'])` - `load_prescriptions()`**:
    - 기능: AJAX 요청을 통해 환자의 진료과에 해당하는 처방 목록과 총액을 불러옵니다.
    - GET:
        1. 세션에서 `patient_rrn`과 `patient_name`을 확인합니다. 없으면 오류 응답을 반환합니다.
        2. `reception_service.lookup_reservation`으로 예약 정보를 조회하여 진료과(`department`)를 확인합니다. 없으면 오류 응답을 반환합니다.
        3. `payment_service.load_department_prescriptions`를 호출하여 해당 진료과의 처방 항목(이름, 비용 포함)과 총액을 가져옵니다.
            - 이 서비스는 `data/treatment_fees.csv`에서 해당 진료과에 대한 항목들을 무작위(2-3개)로 선택하고 총액을 계산합니다.
        4. 처방명 리스트(`prescription_names`)와 총액(`total_fee`)은 다음 단계(증명서 발급 등)를 위해 세션(`last_prescriptions`, `last_total_fee`)에 저장합니다.
        5. 처방 상세 내역(`prescriptions_for_display` - 각 항목명과 비용)과 총액을 JSON 형태로 반환하여 결제 페이지에 표시합니다.
        6. 서비스에서 오류 발생 시 (예: 데이터 파일 없음, 해당 진료과 처방 없음), 오류 메시지를 JSON으로 반환합니다.

- **`@payment_bp.route('/done')` - `done()`**:
    - 기능: 결제 완료 정보를 표시합니다.
    - GET:
        1. 쿼리 파라미터에서 `pay_id`를 가져옵니다.
        2. `payment_service.get_payment_details`를 호출하여 해당 `pay_id`의 결제 기록(ID, 금액, 방법 등)을 조회합니다.
        3. 결제 기록이 없으면 수납 초기 화면으로 리다이렉트합니다.
        4. `payment.html`을 `done` 단계로 렌더링하며 결제 완료 정보를 전달합니다.

### 서비스 (`app/services/payment_service.py`)

- **`process_new_payment(patient_id, amount, method)`**:
    - 새로운 결제 요청을 처리합니다.
    - 고유한 `payment_id` (UUID)를 생성합니다.
    - 결제 정보를 (환자 ID, 금액, 방법, 상태 'completed', 타임스탬프) 딕셔너리로 만들어 내부 `_payments_db` 리스트에 저장합니다. (현재는 메모리 내 저장)
    - `payment_id`를 반환합니다.

- **`get_payment_details(payment_id)`**:
    - `_payments_db`에서 주어진 `payment_id`에 해당하는 결제 기록을 찾아 반환합니다. 없으면 `None`을 반환합니다.

- **`update_reservation_with_payment_details(patient_rrn, prescription_names, total_fee)`**:
    - `data/reservations.csv` 파일을 업데이트합니다.
    - 주어진 `patient_rrn`에 해당하는 예약을 찾아 `prescription_names` (쉼표로 구분된 문자열), `total_fee` (문자열), 그리고 `status`를 'Paid'로 업데이트합니다.
    - 파일이 없거나, 필수 컬럼(rrn, prescription_names, total_fee)이 없거나, 해당 rrn을 찾지 못하면 False를 반환합니다. 성공 시 True 반환.

- **`load_department_prescriptions(department)`**:
    - `data/treatment_fees.csv`에서 특정 진료과(`department`)의 처방 목록을 불러옵니다.
    - 해당 과의 모든 처방을 읽어들인 후, 2개 또는 3개의 항목을 무작위로 선택합니다 (항목이 1개면 1개 선택).
    - 선택된 처방들의 총액을 계산합니다.
    - 반환 값: 딕셔너리 형태
        - `prescriptions_for_display`: 선택된 각 처방의 이름(`name`)과 비용(`fee`)을 담은 리스트 (화면 표시용)
        - `prescription_names`: 선택된 각 처방의 이름만 담은 리스트 (세션 저장 및 증명서 데이터용)
        - `total_fee`: 총액
    - `treatment_fees.csv` 파일이 없거나, 해당 진료과에 처방이 없거나, 데이터에 오류가 있으면 `error` 키를 포함한 딕셔너리를 반환합니다.

### 템플릿 (`templates/payment.html`)
- JavaScript (`static/js/payment.js`)와 연동하여 동적으로 처방을 불러오고 UI를 업데이트합니다.
- `step` 변수 값에 따라 표시 내용이 달라집니다:
    - `initial_payment`: 초기 화면. "처방전 불러오기" 버튼 표시. (JavaScript가 자동으로 클릭 트리거 가능)
    - (JavaScript에 의해 동적 업데이트): 처방전 목록과 총액, 결제 방법(카드/현금) 선택 버튼 표시.
    - `done`: 결제 완료 화면. 결제 ID, 금액, 방법 등 표시.
- 오류 메시지 표시 영역 (예: 세션 만료, 데이터 누락).
- '처음으로' 버튼.

---
## 5. 증명서 발급 기능

### 라우트 (`app/routes/certificate.py`)

- **`@certificate_bp.route('/')` - `certificate()`**:
    - 기능: 증명서 발급 종류 선택 화면을 렌더링합니다.
    - GET: `templates/certificate.html`을 렌더링합니다. 이 페이지에는 처방전 발급, 진료확인서 발급 등의 버튼이 있습니다.

- **`@certificate_bp.route('/prescription/')` - `generate_prescription_pdf()`**:
    - 기능: 처방전 PDF를 생성하여 반환합니다.
    - GET:
        1. 세션에서 `patient_name`, `patient_rrn`을 가져옵니다. 없으면 접수 페이지로 리다이렉트합니다.
        2. `reception_service.lookup_reservation`으로 예약 정보를 조회하여 진료과(`department`)를 확인합니다. 예약 또는 진료과 정보가 없으면 적절한 오류와 함께 접수 페이지로 리다이렉트합니다.
        3. `certificate_service.get_prescription_data_for_pdf`를 호출하여 PDF 생성에 필요한 데이터 (의사명, 처방내역, 총액, 발행일 등)를 가져옵니다.
            - 이 서비스는 `reservations.csv`에서 환자의 수납 상태('Paid'), 처방명, 총액 등을 확인합니다.
            - 수납 미완료, 결제 금액 0원 이하 등의 경우 오류 상태 코드와 메시지를 반환합니다.
        4. 서비스로부터 `OK` 상태 코드를 받으면, `certificate_service.prepare_prescription_pdf`를 호출하여 PDF 바이트와 파일명을 생성합니다.
            - 이 서비스는 내부적으로 `app/utils/pdf_generator.create_prescription_pdf_bytes`를 사용합니다.
        5. 생성된 PDF를 브라우저에서 인라인으로 보거나 다운로드할 수 있도록 `Response` 객체로 반환합니다.
        6. `get_prescription_data_for_pdf`에서 오류 상태 코드를 받으면, 해당 오류 메시지를 포함한 `error.html`을 렌더링합니다.
        7. PDF 생성 중 `MissingKoreanFontError` 발생 시에도 `error.html`을 렌더링합니다.

- **`@certificate_bp.route('/medical_confirmation/')` - `generate_confirmation_pdf()`**:
    - 기능: 진료확인서 PDF를 생성하여 반환합니다.
    - GET:
        1. 세션에서 `patient_name`, `patient_rrn`을 가져옵니다. 없으면 접수 페이지로 리다이렉트합니다.
        2. `reception_service.lookup_reservation`으로 예약 정보를 조회하여 진료과(`department`)를 가져옵니다. 이 진료과명은 진료확인서의 '병명'으로 사용됩니다.
        3. `certificate_service.prepare_medical_confirmation_pdf`를 호출하여 PDF 바이트와 파일명을 생성합니다.
            - 이 서비스는 내부적으로 `app/utils/pdf_generator.create_confirmation_pdf_bytes`를 사용하며, 진단일은 임의로 설정합니다.
        4. 생성된 PDF를 `Response` 객체로 반환합니다.
        5. `MissingKoreanFontError` 발생 시 `error.html`을 렌더링합니다.

### 서비스 (`app/services/certificate_service.py`)

- **`get_prescription_data_for_pdf(patient_rrn, department)`**:
    - `data/reservations.csv`에서 `patient_rrn`으로 예약 정보를 조회합니다.
    - 파일/예약 정보 부재, 접수 미완료 (`Pending`), 수납 미완료 (`Registered` 또는 'Paid'가 아닌 상태), 또는 결제 금액이 0 이하인 경우 적절한 상태 코드와 메시지를 반환합니다.
    - 정상 수납 완료된 경우(`Paid` 상태이고 `total_fee` > 0):
        - 예약된 의사명, 발행일(예약일자 기준), 처방명 리스트(문자열에서 파싱)를 추출합니다.
        - `data/treatment_fees.csv`에서 각 처방명의 비용을 조회하여 처방 상세 리스트(`selected_prescriptions`)를 구성합니다.
        - PDF 생성에 필요한 데이터 (의사명, 의사면허번호(임의), 진료과, 처방 상세, 총액, 발행일)를 담은 딕셔너리와 함께 `OK` 상태 코드를 반환합니다.

- **`prepare_prescription_pdf(patient_name, patient_rrn, department, prescription_details)`**:
    - `get_prescription_data_for_pdf`로부터 받은 `prescription_details`에 환자 이름과 주민번호를 추가합니다.
    - `app/utils/pdf_generator.create_prescription_pdf_bytes`를 호출하여 PDF 바이트를 생성합니다.
    - 파일명 (예: `prescription_환자명_타임스탬프.pdf`)을 생성하여 PDF 바이트와 함께 반환합니다.
    - `prescription_details`가 없으면 `None, None`을 반환합니다.

- **`prepare_medical_confirmation_pdf(patient_name, patient_rrn, disease_name)`**:
    - 진단일(임의의 과거 날짜)과 발행일(현재 날짜)을 설정합니다.
    - `app/utils/pdf_generator.create_confirmation_pdf_bytes`를 호출하여 PDF 바이트를 생성합니다. (이때 `disease_name`은 보통 진료과명으로 전달됩니다.)
    - 파일명 (예: `medical_confirmation_환자명_타임스탬프.pdf`)을 생성하여 PDF 바이트와 함께 반환합니다.

### 유틸리티 (`app/utils/pdf_generator.py`)
- **`MissingKoreanFontError`**: 한글 폰트 파일(`NanumSquareNeo-bRg.ttf`)을 찾을 수 없을 때 발생하는 사용자 정의 예외입니다.
- **`_add_korean_font(pdf_instance)`**: FPDF 인스턴스에 한글 폰트(나눔스퀘어 네오)를 추가하고 기본 폰트로 설정합니다. 폰트 파일이 없으면 `MissingKoreanFontError`를 발생시킵니다.
- **`create_prescription_pdf_bytes(...)`**:
    - FPDF를 사용하여 처방전 PDF 내용을 구성하고 바이트 형태로 반환합니다.
    - 포함 정보: 발행일, 기관명, 환자 정보, 진료과, 처방내역(항목, 금액), 총계, 의사명.
    - 모든 텍스트 표시에 한글 폰트를 사용합니다.
- **`create_confirmation_pdf_bytes(...)`**:
    - FPDF를 사용하여 진료확인서 PDF 내용을 구성하고 바이트 형태로 반환합니다.
    - 포함 정보: 발행일, 기관명, 환자 정보, 진단명(병명), 진료일(진단일), 확인 문구, 담당의사명.
    - 모든 텍스트 표시에 한글 폰트를 사용합니다.

### 템플릿 (`templates/certificate.html`)
- 증명서 종류 선택 버튼 제공:
    - '처방전 발급': 클릭 시 `certificate.generate_prescription_pdf` 라우트로 이동.
    - '진료확인서 발급': 클릭 시 `certificate.generate_confirmation_pdf` 라우트로 이동.
- (오류 발생 시 `templates/error.html`이 대신 렌더링 될 수 있음)
- '처음으로' 버튼.

---
## 6. AI 챗봇 기능

### 라우트 (`app/routes/chatbot.py`)

- **`@chatbot_bp.route('/interface')` - `chatbot_interface()`**:
    - 기능: AI 챗봇 인터페이스 페이지를 렌더링합니다.
    - GET: `templates/chatbot_interface.html`을 렌더링합니다.

- **`@chatbot_bp.route('/chatbot', methods=['POST'])` - `handle_chatbot_request()`**:
    - 기능: 사용자의 메시지(텍스트 및 선택적 이미지)를 받아 Gemini API를 통해 AI의 응답을 생성하고 반환합니다. 또한, AI의 응답에 따라 내부 서비스(접수, 수납, 증명서 발급)를 호출하고 그 결과를 포함하여 응답할 수 있습니다.
    - POST:
        1. 요청 본문에서 사용자 메시지(`message`)와 선택적 이미지 데이터(`base64_image_data`)를 JSON 형태로 받습니다.
        2. `chatbot_service.generate_chatbot_response`를 호출하여 AI 응답 및 관련 서비스 처리 결과를 가져옵니다.
        3. 서비스 응답을 JSON 형태로 반환합니다. (예: `{'reply': ai_message}` 또는 서비스 처리 결과 포함 `{'reply': ..., 'pdf_filename': ..., 'pdf_data_base64': ...}`)
        4. API 호출 중 또는 서비스 처리 중 오류 발생 시, 적절한 오류 메시지와 상태 코드를 JSON으로 반환합니다.

### 서비스 (`app/services/chatbot_service.py`)

- **`generate_chatbot_response(user_question, base64_image_data)`**:
    - 환경 변수에서 `GEMINI_API_KEY`를 가져와 Gemini 클라이언트를 설정합니다. API 키가 없으면 오류를 반환합니다.
    - `gemini-1.5-flash-latest` 모델을 사용합니다.
    - `SYSTEM_INSTRUCTION_PROMPT` (시스템 프롬프트)와 사용자 질문, 그리고 제공된 경우 이미지 데이터를 함께 모델에 전달합니다.
    - 모델로부터 받은 응답 텍스트를 파싱합니다. 이 응답은 AI가 사용자의 의도를 파악하여 특정 서비스(접수, 수납, 증명서)를 수행해야 한다고 판단한 경우, 해당 서비스의 파라미터를 포함하는 JSON 형식일 수 있습니다.
    - 파싱된 JSON에서 `intent`를 확인합니다:
        - **`general`**: 일반적인 답변(`reply`)을 반환합니다.
        - **`reception`**: `handle_reception_request`를 호출하여 접수 관련 로직을 처리하고 그 결과를 `reply`로 반환합니다.
        - **`payment`**: `handle_payment_request`를 호출하여 수납 관련 로직을 처리하고 그 결과를 `reply`로 반환합니다.
        - **`certificate`**: `handle_certificate_request`를 호출하여 증명서 발급 로직을 처리하고, 성공 시 PDF 파일명과 Base64 인코딩된 PDF 데이터를 `reply`와 함께 반환합니다.
    - 모델 응답 처리 중 또는 각 서비스 핸들러 내부에서 오류 발생 시, 오류 메시지와 상태 코드를 포함한 딕셔너리를 반환합니다.

- **`handle_reception_request(parameters, user_query)`**:
    - Gemini로부터 받은 파라미터 (`name`, `rrn`, `symptom` 등)를 사용하여 접수 로직을 수행합니다.
    - `reception_service.lookup_reservation`으로 기존 예약 확인, `reception_service.new_ticket`으로 새 티켓 발급, `reception_service.update_reservation_status`로 상태 업데이트 등을 수행합니다.
    - 처리 결과에 따라 사용자에게 안내할 메시지(`reply`)를 생성하여 반환합니다.

- **`handle_payment_request(parameters, user_query)`**:
    - 파라미터 (`name`, `rrn`, `payment_stage`, `payment_method` 등)를 사용하여 수납 로직을 수행합니다.
    - `payment_stage`가 'initial'이면 `payment_service.load_department_prescriptions`로 처방 내역을 불러와 안내합니다.
    - `payment_stage`가 'confirmation'이면 `payment_service.update_reservation_with_payment_details`로 결제를 확정하고 예약 정보를 업데이트합니다.
    - 처리 결과에 따라 사용자에게 안내할 메시지(`reply`)를 생성하여 반환합니다.

- **`handle_certificate_request(parameters, user_query)`**:
    - 파라미터 (`name`, `rrn`, `certificate_type`)를 사용하여 증명서 발급 로직을 수행합니다.
    - `certificate_type`에 따라 `certificate_service.get_prescription_data_for_pdf` 및 `certificate_service.prepare_prescription_pdf` (처방전) 또는 `certificate_service.prepare_medical_confirmation_pdf` (진료확인서)를 호출합니다.
    - 성공 시, PDF 파일명, Base64 인코딩된 PDF 데이터와 함께 안내 메시지를 반환합니다. `MissingKoreanFontError` 등 오류 발생 시 적절한 오류 메시지를 반환합니다.

### 템플릿 (`templates/chatbot_interface.html` 내 JavaScript)
- **초기화**:
    - 웹캠 접근 (`setupWebcam`) 및 음성 인식 (`SpeechRecognition`) API 설정.
    - 초기 환영 메시지 표시 및 음성 안내 (`speak` 함수).
- **UI 요소**:
    - 웹캠 영상 표시 영역 (`#webcamFeed`).
    - 대화 내용 표시 영역 (`#chatHistory`).
    - 사용자 입력 필드 (`#userInput`).
    - 전송 버튼 (`#sendMessageBtn`), 음성 입력 토글 버튼 (`#toggleMicBtn`), 이미지 캡처 버튼 (`#captureImageBtn`).
    - 캡처된 이미지 미리보기 (`#capturedImagePreview`).
- **메시지 송수신**:
    - `sendMessage(messageText, base64ImageData)`: 사용자 메시지와 선택적 이미지 데이터를 `/api/chatbot` 엔드포인트로 POST 요청 전송.
    - 응답으로 받은 텍스트는 채팅창에 표시하고, 음성으로도 안내 (`speak` 함수).
    - 응답에 PDF 데이터(`pdf_data_base64`, `pdf_filename`)가 포함된 경우, Base64 디코딩 후 Blob URL을 생성하여 새 창에서 PDF를 엽니다.
- **음성 입출력**:
    - `toggleMicBtn`: 클릭 시 음성 인식 시작/중지. 인식된 텍스트는 입력 필드에 채워짐.
    - `speak(text)`: 주어진 텍스트를 한국어 음성으로 변환하여 출력 (Web Speech API `SpeechSynthesis`).
- **이미지 캡처**:
    - `captureImageBtn`: 클릭 시 현재 웹캠 화면을 캡처하여 Base64 이미지 데이터로 변환, 미리보기에 표시. 이 데이터는 다음 메시지 전송 시 함께 서버로 전달됨.
- **메시지 표시**:
    - `appendMessage(sender, text)`: 채팅창에 사용자, 봇, 또는 시스템 메시지를 적절한 스타일로 추가.

---
## 7. JavaScript 상호작용 (`static/js/script.js` 및 `templates/base.html` 내 스크립트)

### 공통 스크립트 (주로 `templates/base.html` 내 헤더 버튼 관련)

- **글자 크기 조절**:
    - 헤더의 '가/', '가', '가+' 버튼 클릭 시 `home.set_font` 라우트 (`/set_font/<size>`)를 호출합니다.
    - 이 라우트는 선택된 글꼴 크기 (`small`, `normal`, `large`)를 세션에 저장합니다.
    - `base.html`의 `<body>` 태그는 세션에 저장된 `font_size` 값에 따라 동적으로 CSS 클래스 (`font-small`, `font-normal`, `font-large`)를 적용받습니다.
    - 해당 클래스에 대한 스타일은 `static/css/style.css`에 정의되어 있어 전체 페이지 글꼴 크기가 조절됩니다. (실제 `script.js`에는 localStorage 사용 로직은 없으며, Flask 세션을 통해 처리)

- **언어 변경**:
    - 헤더의 언어 변경 버튼 (현재 언어에 따라 'English' 또는 '한국어' 표시) 클릭 시 `home.switch_language` 라우트 (`/switch_lang`)를 호출합니다.
    - 이 라우트는 세션에 저장된 언어 코드 (`ko` <-> `en`)를 변경합니다.
    - Flask-Babel이 세션의 언어 설정에 따라 이후 모든 페이지에서 적절한 번역을 제공합니다.

- **TTS 재생**:
    - 헤더의 'TTS' 버튼 클릭 시 `playTTS(document.title)` 함수 (현재 `script.js`에 정의)를 호출합니다.
    - 이 함수는 `/tts?text=<페이지제목>` 엔드포인트로 GET 요청을 보내고, 응답으로 받은 오디오 Blob을 재생합니다. (해당 `/tts` 라우트는 현재 코드베이스에 정의되어 있지 않음. 문서화 시점에서는 기능 불완전 가능성)

- **지도 이미지 열기**:
    - 헤더의 '지도' 버튼 클릭 시 `openMap()` 함수 (현재 `script.js`에 정의)를 호출합니다.
    - 이 함수는 `/static/images/map/clinic_map.png` 경로의 지도 이미지를 새 창이나 탭에서 엽니다.

- **자동 홈 화면 이동 타이머**:
    - `script.js` 상단에 120초 (2분) 후 자동으로 홈 화면 (`/home`)으로 리다이렉션하는 타이머 설정.
    - 문서 내 클릭 이벤트 발생 시 타이머를 리셋하여 다시 120초를 카운트합니다.

### AI 챗봇 모달 제어 (주로 `static/js/script.js` 내)

- **챗봇 모달 열기/닫기**:
    - 우측 하단의 'AI' 버튼 (`#aiChatbotInvokeButton`) 클릭 시 `openAiChatbot()` 함수 호출.
        - 모달 창 (`#aiChatbotModal`)을 표시 (`display: flex`).
        - 챗봇 웹캠 기능 시작 시도 (`startChatbotWebcam`, 현재는 플레이스홀더 텍스트만 변경).
        - 음성 인식 기능 초기화 (`initializeChatbotSpeechRecognition`).
        - 채팅창이 비어있으면 초기 환영 메시지 추가 및 음성 안내.
    - 모달 내 'X' 버튼 (`#aiChatbotCloseButton`) 클릭 시 `closeAiChatbot()` 함수 호출.
        - 모달 창 숨김 (`display: none`).
        - 웹캠 기능 중지 시도 (`stopChatbotWebcam`).
        - 음성 인식 및 음성 합성 중지.

- **챗봇 메시지 처리**:
    - `askAiChatbot(query)`: 사용자 입력(`query`)을 `/api/chatbot` (실제로는 `chatbot_bp`에 의해 `/api/chatbot`으로 매핑된 `handle_chatbot_request` 라우트)으로 전송하고 응답을 받아 `addMessageToChatbot`으로 표시.
    - `addMessageToChatbot(text, sender)`: 챗봇 메시지를 UI에 추가하고, 봇 메시지인 경우 음성으로도 출력 (`chatbotSpeak`).
    - 음성 인식 (`speechRecognition.onresult`) 결과로 `askAiChatbot` 호출 가능.

- **음성 합성 (TTS)**:
    - `chatbotSpeak(text, instant)`: 챗봇의 응답을 음성으로 변환하여 재생 (Web Speech API `SpeechSynthesis`). `instant` 파라미터로 즉시 재생 여부 제어. 한국어 목소리 우선 사용.

- **음성 인식 (STT)**:
    - `initializeChatbotSpeechRecognition()`: Web Speech API (`webkitSpeechRecognition`) 설정. 한국어 인식.
    - (챗봇 모달 내에는 별도 STT 버튼이 없고, `chatbot_interface.html`의 자체 스크립트가 마이크 버튼을 통해 STT를 직접 제어함. `script.js`의 STT는 `chatbot_interface.html`의 것과 별개로 보임. 문서화 시점에서는 `chatbot_interface.html`의 JavaScript가 우선적으로 챗봇 인터페이스 내 STT를 담당)

### 기능별 JavaScript (각 템플릿 내)

- **챗봇 (`templates/chatbot_interface.html` 내 스크립트)**:
    - 위의 "AI 챗봇 기능" 섹션의 템플릿 설명에서 이미 상세히 기술됨. (웹캠, STT, TTS, 메시지/이미지 전송, PDF 표시 등)

- **홈 화면 오디오 자동 재생 (`templates/home.html` 내 스크립트)**:
    - 페이지 로드 시 환영 음성 (`#welcome-audio`) 자동 재생 시도.
    - 브라우저 정책으로 자동 재생 실패 시, 사용자의 첫 클릭 이벤트 발생 시 오디오 재생을 다시 시도.
