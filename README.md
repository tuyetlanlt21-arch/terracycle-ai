# TerraCycle AI

**Hỗ trợ lựa chọn luân canh cây trồng dựa trên dữ liệu khí hậu lịch sử và điều kiện canh tác.**

TerraCycle AI là nguyên mẫu cho NASA Space Apps 2026 — Field Shift, với điểm thí điểm tại Long Xuyên, An Giang. Dự án giúp người dùng so sánh các phương án luân canh, xem căn cứ đánh giá và nhận diện dữ liệu còn thiếu trước khi xuống giống.

**[Trải nghiệm demo trên Vercel →](https://terracycle-ai.vercel.app/)**

## Tính năng

- Nhập hồ sơ nông trại: cây trồng hiện tại, diện tích, ngày gieo trồng và ưu tiên canh tác.
- Bổ sung dữ liệu đo tại ruộng như pH đất, độ mặn đất, độ mặn nước tưới và điều kiện cấp thoát nước.
- So sánh ba chiến lược: canh tác hiện tại (`current_practice`), tiết kiệm nước (`water_saving`) và phục hồi đất (`soil_recovery`).
- Đối chiếu cửa sổ sinh trưởng với dữ liệu NASA POWER và các quy tắc cây trồng có nguồn tham chiếu.
- Hiển thị lý do đánh giá, phương án bị loại, nguồn dữ liệu và trạng thái `PASS`, `FAIL` hoặc `UNKNOWN`.

## Dữ liệu và phạm vi đánh giá

| Nguồn | Vai trò |
| --- | --- |
| NASA POWER | Dữ liệu khí hậu lịch sử: nhiệt độ, mưa, độ ẩm, bức xạ mặt trời và gió. Giao diện sử dụng bộ dữ liệu thí điểm cho giai đoạn 2020–2025. |
| ISRIC SoilGrids | Adapter lấy thuộc tính đất mô hình hóa; hệ thống ghi nhận rõ khi nguồn không khả dụng. |
| Danh mục cây trồng và quy tắc luân canh | Các bản ghi, ngưỡng và quy tắc có nguồn trong `data/reference/`; adapter ECOCROP chuẩn hóa dữ liệu xuất khi được cung cấp. |
| Người dùng / đo đạc địa phương | pH, độ mặn đất, độ mặn nước tưới và điều kiện canh tác thực tế. |

NASA POWER cung cấp bối cảnh lịch sử, **không phải dự báo thời tiết**. Độ mặn đất và nước tưới không được suy ra từ SoilGrids. Dữ liệu chưa biết được giữ nguyên là `UNKNOWN`; hệ thống không tự điền các giá trị khoa học còn thiếu.

Các chiến lược hiện tại mang tính minh họa, sử dụng quy tắc xác định. Tên chiến lược không đồng nghĩa với hiệu quả tiết kiệm nước hay phục hồi đất đã được đo lường. Xem thêm [nguồn dữ liệu và giới hạn](docs/data-sources.md).

## Công nghệ

- **Frontend:** React 18, TypeScript, Vite, Lucide React.
- **Backend:** Python 3.12, FastAPI, Pydantic, Uvicorn.
- **Data science:** pandas, requests, các adapter NASA POWER, SoilGrids và ECOCROP.
- **Kiểm tra:** pytest, Node.js test runner và GitHub Actions.

## Cấu trúc dự án

```text
terracycle-ai/
├── frontend/       # Giao diện nhập hồ sơ và so sánh chiến lược
├── backend/        # FastAPI, hợp đồng API và logic đánh giá
├── datascience/    # Pipeline dữ liệu và bộ đánh giá luân canh
├── data/           # Dữ liệu tham chiếu và dữ liệu đã xử lý
├── shared/         # Fixture và dữ liệu dùng chung
├── docs/           # Kiến trúc, hướng dẫn và báo cáo kiểm thử
└── .github/        # CI và workflow auto-merge
```

## Chạy trên máy

Yêu cầu: **Python 3.12**, **Node.js 22** và **npm**. Các lệnh dưới đây dùng PowerShell, chạy từ thư mục gốc của repository.

### 1. Backend

```powershell
py -3.12 -m venv .venv
Copy-Item backend/.env.example backend/.env
& .venv/Scripts/python.exe -m pip install -r backend/requirements.txt -r datascience/requirements.txt
& .venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --env-file backend/.env --reload --host 127.0.0.1 --port 8000
```

- API: <http://localhost:8000>
- Swagger UI: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>

Hướng dẫn Linux/macOS và Docker nằm trong [backend/README.md](backend/README.md).

### 2. Frontend

Mở terminal thứ hai:

```powershell
cd frontend
Copy-Item .env.example .env
npm ci
npm run dev
```

Mở địa chỉ Vite hiển thị trong terminal, mặc định là <http://localhost:5173>.

### 3. Sử dụng

1. Mở **Farm Profile**, nhập cây trồng hiện tại, diện tích, ngày gieo trồng và ưu tiên.
2. Chọn ngày gieo trồng trong giai đoạn lịch sử 2020–2025 mà giao diện hỗ trợ.
3. Bổ sung các chỉ số đo thực tế nếu có; để trống dữ liệu chưa biết.
4. Chọn **Compare three strategies** và đọc căn cứ của từng phương án. `UNKNOWN` cho biết cần thêm bằng chứng để đánh giá.

## Cấu hình triển khai

Frontend demo được triển khai tại **[terracycle-ai.vercel.app](https://terracycle-ai.vercel.app/)**. Backend cần được triển khai riêng để phục vụ các yêu cầu API.

| Thành phần | Biến môi trường | Cấu hình |
| --- | --- | --- |
| Frontend | `VITE_API_BASE_URL` | URL HTTPS công khai của backend, đặt trước khi build. Local dùng `http://localhost:8000`. |
| Backend | `CORS_ORIGINS` | Danh sách origin frontend được phép, phân cách bằng dấu phẩy. Với demo: `https://terracycle-ai.vercel.app`. |

Build production của frontend không tự chuyển về localhost. Lưu cấu hình production trong phần environment của nền tảng hosting; không commit file `.env` hoặc khóa API.

## Kiểm tra

Từ thư mục gốc, sau khi cài các dependency ở trên:

```powershell
& .venv/Scripts/python.exe -m pytest backend/tests datascience/tests -q
```

Kiểm tra frontend:

```powershell
cd frontend
npm test
npm run build
```

GitHub Actions chạy kiểm thử backend/data science, kiểm thử frontend và build frontend khi có pull request hoặc push vào các nhánh được cấu hình.

## API chính

| Phương thức | Endpoint | Chức năng |
| --- | --- | --- |
| `GET` | `/health` | Kiểm tra trạng thái dịch vụ |
| `GET` | `/api/crops` | Lấy danh mục cây trồng |
| `GET` | `/api/soil/profile` | Lấy hồ sơ đất và trạng thái dữ liệu |
| `GET` | `/api/climate/summary` | Lấy tóm tắt khí hậu lịch sử |
| `POST` | `/api/rotations/compare` | Đánh giá chiến lược theo hồ sơ nông trại |

Xem schema yêu cầu và phản hồi tại Swagger UI khi backend đang chạy.

## Tài liệu liên quan

- [Kiến trúc hệ thống](docs/ARCHITECTURE.md)
- [Hướng dẫn phát triển](docs/DEVELOPMENT.md)
- [Thiết lập backend và Docker](backend/README.md)
- [Pipeline và nguyên tắc đánh giá dữ liệu](datascience/README.md)
- [Nguồn dữ liệu và giới hạn](docs/data-sources.md)
- [Dữ liệu dùng chung](shared/README.md)

## CI và auto-merge

Để dùng auto-merge, quản trị viên cần cấu hình nhánh `main` yêu cầu pull request và các check `backend`, `frontend`; bật yêu cầu cập nhật nhánh trước khi merge, giữ các yêu cầu review hiện có và bật **Allow auto-merge** trong cài đặt repository.

Tạo nhãn `automerge`, sau đó gắn vào PR đã sẵn sàng, cùng repository và hướng đến `main` khi CI hoặc review bắt buộc còn đang chờ. Workflow sẽ yêu cầu GitHub tự squash merge khi đủ điều kiện. Nếu PR đã đủ điều kiện merge ngay, dùng nút merge thông thường. Để hủy yêu cầu đã đăng ký, chọn **Disable auto-merge** trên PR; chỉ gỡ nhãn không hủy yêu cầu đó.
