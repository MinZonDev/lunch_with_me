# 🍱 Lunch With Me

Hệ thống đặt cơm trưa nội bộ cho nhóm — tự chọn món, chia tiền tự động, theo dõi số dư.

---

## Tính năng

**Cho thành viên**
- Đăng ký / đăng nhập, quên mật khẩu qua email
- Chọn món hàng ngày (thường hoặc chay) trước deadline
- Xem danh sách ai đã chọn, ai chưa chọn
- Yêu cầu nạp tiền — chờ admin duyệt
- Xem số dư, lịch sử nạp và chi tiêu của bản thân

**Cho admin**
- Tạo order hàng ngày, chọn quán ăn, thiết lập deadline
- Quản lý danh sách link đặt món (nhiều link mỗi ngày — ví dụ 1 link quán thường, 1 link quán chay)
- Khoá / mở lại order
- Chốt bill và chia tiền tự động cho từng người
- Duyệt yêu cầu nạp tiền của thành viên
- Thêm khoản chi ngoài (trừ thẳng vào số dư)
- Quản lý danh sách quán ăn (tên + link menu)
- Xem báo cáo tổng hợp theo tháng
- Import lịch sử qua file Excel
- Nhắc nhở tự động qua email (chưa chọn món, sắp hết deadline, số dư thấp)
- Gửi sao kê tháng qua email

---

## Tech Stack

| Layer | Công nghệ |
|---|---|
| Backend | Python · FastAPI · Firebase Firestore |
| Frontend | Next.js 15 (App Router) · plain CSS |
| Auth | JWT (python-jose) · bcrypt |
| Database | Google Firebase Firestore (NoSQL) |
| Email | Gmail SMTP (App Password) |
| Jobs | APScheduler (nhắc nhở, sao kê tự động) |

---

## Cấu trúc thư mục

```
lunch_with_me/
├── backend/
│   ├── app/
│   │   ├── core/          # auth, config
│   │   ├── routers/       # auth, orders, order_items, deposits,
│   │   │                  # members, restaurants, reviews, reports, admin
│   │   ├── services/      # email, scheduler, cost_calculator,
│   │   │                  # report_generator, excel_importer
│   │   ├── database.py    # Firestore client + helpers
│   │   ├── schemas.py     # Pydantic models
│   │   └── main.py
│   ├── seed.py            # Tạo tài khoản admin mặc định
│   ├── Dockerfile
│   └── requirements.txt
└── frontend/
    └── src/
        ├── app/           # Next.js App Router pages
        │   ├── page.js                  # Trang chủ — order hôm nay
        │   ├── order/[id]/page.js       # Chi tiết order
        │   ├── deposit/page.js          # Deposit & số dư
        │   ├── history/page.js          # Lịch sử orders
        │   ├── reports/page.js          # Báo cáo tháng
        │   ├── reviews/page.js          # Review món ăn
        │   ├── admin/                   # Trang quản trị
        │   ├── login/page.js
        │   ├── register/page.js
        │   ├── forgot-password/page.js
        │   └── reset-password/page.js
        ├── components/    # AuthGuard, Sidebar, Toast
        └── lib/           # api.js, auth.js
```

---

## Cài đặt & chạy local

### Yêu cầu

- Python 3.11+
- Node.js 18+
- Tài khoản Firebase (tạo miễn phí tại [firebase.google.com](https://firebase.google.com))

### 1. Firebase setup

1. Vào [Firebase Console](https://console.firebase.google.com) → tạo project mới
2. Chọn **Firestore Database** → tạo database (chế độ **production**)
3. Vào **Project Settings → Service Accounts → Generate new private key**
4. Lưu file JSON tải về (ví dụ: `serviceAccountKey.json`) — **không commit file này**

### 2. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# hoặc: source venv/bin/activate  # macOS/Linux

pip install -r requirements.txt

# Tạo file .env từ mẫu
cp .env.example .env
# Điền FIREBASE_CREDENTIALS_PATH và các biến khác vào .env

# Seed tài khoản admin mặc định
python seed.py

# Chạy server
uvicorn app.main:app --reload --port 8000
```

API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### 3. Frontend

```bash
cd frontend
npm install

# Tạo file .env.local
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local

npm run dev
```

Mở [http://localhost:3000](http://localhost:3000)

### 4. Đăng nhập lần đầu

Tài khoản admin mặc định sau khi chạy `seed.py`:
- Username: `admin`
- Password: `admin123`

> **Đổi mật khẩu ngay sau khi đăng nhập lần đầu.**

---

## Biến môi trường (`backend/.env`)

| Biến | Mô tả | Bắt buộc |
|---|---|---|
| `FIREBASE_CREDENTIALS_PATH` | Đường dẫn tới file Service Account JSON | ✅ |
| `JWT_SECRET` | Chuỗi bí mật ký JWT — tối thiểu 32 ký tự random | ✅ |
| `JWT_EXPIRE_HOURS` | Thời gian hết hạn token (mặc định: `8`) | |
| `SMTP_USER` | Gmail gửi thông báo | |
| `SMTP_PASSWORD` | App Password của Gmail (không phải mật khẩu thường) | |
| `FRONTEND_URL` | URL frontend — dùng cho link reset mật khẩu (mặc định: `http://localhost:3000`) | |
| `LOW_BALANCE_THRESHOLD` | Ngưỡng cảnh báo số dư thấp, đơn vị nghìn đồng (mặc định: `50`) | |
| `ORDER_DEADLINE_DEFAULT` | Giờ khoá order mặc định (mặc định: `11:30`) | |

**Cấu hình Gmail App Password:**
1. Bật 2-Step Verification trên tài khoản Google
2. Vào [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Tạo App Password → dán vào `SMTP_PASSWORD`

---

## Firestore collections

| Collection | Mô tả |
|---|---|
| `users` | Tài khoản đăng nhập |
| `members` | Thành viên ăn trưa (tự tạo khi user đăng ký) |
| `daily_orders` | Order theo ngày |
| `order_items` | Lựa chọn món của từng người trong mỗi order |
| `deposits` | Giao dịch nạp tiền và khoản chi ngoài |
| `restaurants` | Danh sách quán ăn |
| `reviews` | Review món ăn |
| `password_reset_tokens` | Token đặt lại mật khẩu (hết hạn sau 1 giờ) |
| `_counters` | Bộ đếm ID tự tăng (transactional) |

---

## Deploy

### Backend — Docker

```bash
cd backend
docker build -t lunch-backend .
docker run -p 8000:8000 \
  -e FIREBASE_CREDENTIALS_PATH=/app/key.json \
  -v /path/to/serviceAccountKey.json:/app/key.json \
  -e JWT_SECRET=your-secret \
  lunch-backend
```

Hoặc deploy lên **Cloud Run** với `GOOGLE_APPLICATION_CREDENTIALS` nếu chạy trên GCP.

### Frontend — Vercel / static

```bash
cd frontend
npm run build
# Deploy thư mục .next lên Vercel, Netlify, hoặc tự host
```

---

## Lưu ý bảo mật

- **Không bao giờ commit** file `serviceAccountKey.json` hay `.env` lên git — đã có trong `.gitignore`
- Đổi `JWT_SECRET` thành chuỗi random dài trước khi deploy production
- Đổi mật khẩu `admin` ngay sau khi chạy seed
- Gmail App Password chỉ dùng cho ứng dụng này, có thể thu hồi bất cứ lúc nào
