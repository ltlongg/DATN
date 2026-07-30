# Plan: Đăng ký công khai + Landing page + Đăng nhập Google

> Chốt 2026-07-27. Phạm vi: **cổng vào hệ thống** — trang giới thiệu công khai, đăng ký tài
> khoản, và thêm một cách đăng nhập (Google). KHÔNG đụng orchestrator/RAG/KB Inspector.
>
> **Trạng thái**: §0 rename role (2026-07-30) · **pha A đăng ký + pha C Google Sign-In: ĐÃ
> CODE XONG 2026-07-30** · **pha B (landing + đổi cây route `/` → `/chat`): HOÃN theo yêu cầu
> user** — chưa làm, `/` vẫn là khu hỏi đáp sau `RequireAuth`, `/login` + `/register` là 2
> route công khai duy nhất. Chi tiết lệch so với plan: xem §6 "Đã làm gì".
>
> **Sửa 2026-07-30 sau review** — 4 điểm plan bản đầu SAI, đã vá tại chỗ: bỏ auto-link Google
> theo email (§2 Q4 + §4.3.3, lỗ hổng chiếm tài khoản), chuẩn hoá email ở tầng repo (§4.4),
> mật khẩu đếm **byte** chứ không đếm ký tự (§4.2), và sửa bug `client.ts` nuốt mọi lỗi 401
> (§5.1.1 — bug đang chạy, không phải rủi ro tương lai). Thêm §6b rate limit — **đã chốt
> HOÃN**, không nằm trong 3 pha; làm trước khi deploy ra ngoài localhost.

## 0. Đổi tên role `teacher` → `user` (ĐÃ XONG 2026-07-30)

Làm **trước** pha A vì `POST /register` phải biết gán role tên gì. Không phải việc của tính
năng đăng ký, nhưng đứng chắn đường nó.

| Nơi | Sửa gì |
|---|---|
| [common.py](../../apps/backend/app/schemas/common.py) | `Role = Literal["admin", "user"]` |
| [seed_users.py](../../apps/backend/scripts/seed_users.py) | user demo → `user@example.com` / `user123`, role `"user"` |
| `LogsFilterBar.tsx` | placeholder ô lọc email |
| `documents.py`, `inspect.py` | comment nói về role |
| [types/index.ts](../../apps/frontend/src/types/index.ts) | `Role = "admin" \| "user"` |
| `UserFormModal.tsx` | `ROLES` + 2 giá trị khởi tạo state |
| 17 file `tests/` + `AppSidebar.test.tsx` | fixture key `"teacher"` → `"user"`, email test `user-test@example.com` |

**Dữ liệu cũ: XOÁ, không migrate** (quyết định user 2026-07-30 — "dev data test lại là có").
Bản đầu của mục này dùng `UPDATE users SET role='user' WHERE role='teacher'` nhét trong
`SCHEMA_STATEMENTS`; đã **gỡ bỏ**. Lý do phải làm *một trong hai*: `Role` giờ là
`Literal["admin","user"]` nên mỗi row còn `role='teacher'` sẽ làm Pydantic ném
`ValidationError` **lúc đọc** — `/admin/users` trả 500 và chính user đó không đăng nhập được.

Đã xoá, **đúng phạm vi tài khoản `teacher@example.com`**, trong 1 transaction:

| Xoá | Số dòng |
|---|---|
| `users` (→ CASCADE `conversations` → `messages`) | 1 → 13 → 50 |
| `llm_usage` gắn với 13 hội thoại đó | 55 |
| `activity_log` mang `user_id` đó | 220 |

**`admin@example.com` giữ nguyên** (17 hội thoại / 50 message / 1046 activity) → các màn
`/admin/logs`, `/admin/cost`, `/admin/activity` vẫn có dữ liệu thật để xem, không trống trơn.
Sau đó seed lại `user@example.com` / `user123`.

Nhờ xoá thay vì migrate, **code không còn vết tích gì của `teacher`** — không có dòng DML nào
lẫn trong danh sách DDL của `db.py`.

**Các plan doc CŨ vẫn viết "teacher"** (`backend-plan.md`, `frontend-plan.md`,
`citation-viewer-plan.md`, `backend-additions-plan.md`, `system-config-plan.md`) — giữ nguyên
như bản ghi lịch sử, KHÔNG sửa lại. Đọc là "role người dùng thường", giờ tên `user`.
Ngược lại `README.md`, `docs/design/frontend-scope.md` và `CLAUDE.md` (mục `### Role`) **đã
đổi** vì là tài liệu scope đang sống, người mới đọc trước tiên.

## 1. Hiện trạng

| Hạng mục | Trạng thái | Nơi |
|---|---|---|
| Đăng nhập email/mật khẩu | ✅ Xong, không sửa lại | [auth.py](../../apps/backend/app/api/auth.py), [LoginPage.tsx](../../apps/frontend/src/pages/LoginPage.tsx) |
| Đăng ký công khai | ❌ Chưa có | — |
| Đăng nhập Google | ❌ Chưa có | — |
| Landing page | ❌ Chưa có | — |

Ba điểm cần biết trước khi đọc tiếp:

- **Tạo tài khoản hiện chỉ có 2 đường**: admin bấm ở `/admin/users` (`POST /api/admin/users`,
  gác `require_admin` — [users.py:42](../../apps/backend/app/api/users.py#L42)) hoặc chạy tay
  `scripts/seed_users.py`. Người ngoài không tự tạo được.
- **`/` đang nằm sau `RequireAuth`** ([routes.tsx:31](../../apps/frontend/src/app/routes.tsx#L31)):
  khách chưa đăng nhập gõ domain là bị đá thẳng sang `/login`, và catch-all `*` cũng đổ về `/`.
  Muốn có trang giới thiệu **công khai** thì buộc phải sửa cây route, không né được.
- **`users.password_hash` đang `TEXT NOT NULL`** ([db.py:45](../../apps/backend/app/core/db.py#L45)).
  Tài khoản Google không có mật khẩu → phải nới ràng buộc này (§4.3).

## 2. Chốt thiết kế

**Q1. Chính sách đăng ký → tự do, dùng được ngay.**
Ai đăng ký cũng thành `role="user"`, `is_active=true`, đăng nhập luôn (auto-login sau khi
tạo). Không có bước admin duyệt.
*Đánh đổi đã biết*: mở đăng ký = ai có link cũng tạo được tài khoản và tiêu API cost thật của
đồ án. Giảm thiểu bằng quota — xem §4.2 và §8.

**Q2. Route → `/` là landing công khai, khu hỏi đáp dời sang `/chat`.**
Khách vào domain thấy trang giới thiệu; đã đăng nhập thì header landing đổi nút thành "Vào hỏi
đáp" (KHÔNG auto-redirect — người đã đăng nhập vẫn có quyền xem lại trang giới thiệu).

**Q3. Google Sign-In → dùng luồng ID token (Google Identity Services), KHÔNG dùng luồng
Authorization Code redirect.**

| | ID token (chọn) | Authorization Code redirect |
|---|---|---|
| Client secret trên backend | **Không cần** | Cần |
| Redirect URI + route callback | **Không cần** | Cần |
| State/PKCE chống CSRF | **Không cần** (token gửi thẳng qua POST) | Cần |
| Backend làm gì | Verify 1 JWT | Đổi code → token → gọi userinfo |
| Lấy được gì | `sub`, `email`, `email_verified`, `name`, `picture` | Như trên + refresh token |

Mình chỉ cần **danh tính** (không đọc Drive/Calendar của người dùng, không cần offline access)
→ luồng ID token là đúng cỡ. Frontend nhận `credential` (JWT Google ký) từ nút Google, POST
sang backend, backend verify chữ ký rồi cấp **JWT của hệ thống mình** như login thường. Nhờ vậy
`authStore`/`RequireAuth`/`get_current_user` **không phải sửa một dòng nào** — Google chỉ là
thêm một cửa vào, không phải hệ thống phiên thứ hai.

**Q4. Đăng nhập Google KHÔNG tự ghép vào tài khoản mật khẩu cùng email** (sửa 2026-07-30 sau
review). Email đã tồn tại mà chưa liên kết → `409 account_link_required`, KHÔNG cấp token.
Lý do đầy đủ + kịch bản chiếm tài khoản: hộp cảnh báo cuối §4.3.3.

**Trả lời câu "có khó lắm không": không.** Phần code ~150 dòng backend + 1 component frontend.
Phần tốn thời gian thật là bấm trên Google Cloud Console (~15 phút, §4.3.1) và nó **không cần
review/verify của Google** vì chỉ xin scope không nhạy cảm (`openid`, `email`, `profile`).

## 3. Cây route sau khi đổi

```
/                 LandingPage         (CÔNG KHAI)
/login            LoginPage           (CÔNG KHAI, có token -> redirect /chat)
/register         RegisterPage        (CÔNG KHAI, có token -> redirect /chat)
/chat             AskPage             (RequireAuth + AppShell)   <- trước là "/"
/admin/*          ... giữ nguyên      (RequireAuth + RoleGuard + AppShell)
*                 -> redirect "/"     (giữ nguyên đích, nhưng giờ đích là landing)
```

Các chỗ đang hardcode `"/"` phải đổi sang `"/chat"` — **liệt kê đủ, đừng sót**:

| File | Dòng hiện tại | Sửa thành |
|---|---|---|
| [useLogin.ts:20](../../apps/frontend/src/features/auth/useLogin.ts#L20) | `navigate("/")` | `navigate("/chat")` (hoặc `state.from` nếu có) |
| [LoginPage.tsx:10](../../apps/frontend/src/pages/LoginPage.tsx#L10) | `<Navigate to="/">` | `<Navigate to="/chat">` |
| [RoleGuard.tsx:7](../../apps/frontend/src/features/auth/RoleGuard.tsx#L7) | `<Navigate to="/">` | `<Navigate to="/chat">` |
| [AppSidebar.tsx:34](../../apps/frontend/src/components/AppSidebar.tsx#L34) | `to: "/"`, `end: true` | `to: "/chat"` (bỏ `end` cũng được) |
| [routes.tsx](../../apps/frontend/src/app/routes.tsx) | `{ index: true, element: <AskPage/> }` | `{ path: "chat", element: <AskPage/> }` |

`RequireAuth` giữ nguyên logic: nó **đã lưu** `state.from`, còn `useLogin`/`useRegister`/
`GoogleButton` sẽ được sửa để **đọc** nó (hiện chưa ai đọc — xem §5.1.2).

## 4. Backend

### 4.1 File đụng tới

```
app/schemas/auth.py     + RegisterRequest, GoogleLoginRequest
app/api/auth.py         + POST /register, POST /google
app/models/user.py      sửa User model + create_user, + get_user_by_google_sub,
                        + normalize_email áp NGAY TRONG get_user_by_email/create_user (§4.4)
                        (KHÔNG có link_google_sub — MVP không liên kết, xem §4.3.3)
app/core/db.py          + 2 ALTER (google_sub, password_hash DROP NOT NULL)
app/core/config.py      + google_client_id
app/core/security.py    verify_password nhận password_hash | None,
                        + validate_bcrypt_password + gọi nó trong hash_password (§4.2)
app/schemas/user.py     UserCreate.password dùng validate_bcrypt_password (bỏ max_length=200)
requirements.txt        + google-auth>=2.38, cachecontrol (cache cert Google — §4.3.3)
tests/test_auth.py      + ~14 test
```

### 4.2 `POST /api/auth/register`

```python
class RegisterRequest(BaseModel):
    email: EmailStr
    name: str = Field(min_length=2, max_length=80)
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def _fits_bcrypt(cls, v: str) -> str:
        return validate_bcrypt_password(v)
```

**Helper dùng chung, đặt ở `app/core/security.py`** cạnh `hash_password`:

```python
def validate_bcrypt_password(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Mật khẩu quá dài, tối đa 72 byte.")
    return password
```

**Gọi ở CẢ BA chỗ** — cùng lý lẽ với chuẩn hoá email (§4.4): chặn ở một cửa thì cửa còn lại
vẫn hở.

| Chỗ | Vì sao cần |
|---|---|
| `RegisterRequest` | Cửa mới, người dùng tự đặt mật khẩu |
| `UserCreate` (admin) | **Đang để `max_length=200`** ([user.py:26](../../apps/backend/app/schemas/user.py#L26)) → admin tạo mật khẩu 200 ký tự là bị cắt im lặng y hệt |
| `hash_password()` | Lớp phòng thủ cuối — bắt mọi caller viết sau này |

```python
def hash_password(password: str) -> str:
    validate_bcrypt_password(password)          # không còn cắt im lặng
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
```

Bỏ được `[:72]` trong `hash_password` là vì đã từ chối > 72 byte từ trước. Nhưng
**`verify_password` GIỮ NGUYÊN `_prepared` (vẫn cắt)**: hash cũ trong DB được sinh từ bản đã
cắt, bỏ cắt ở khâu verify là **khoá cửa những tài khoản đó**. Validate chặn ở đầu vào, không
đụng đường đối chiếu.

Ở tầng API, `ValueError` từ Pydantic validator ra `422` sẵn. Lời gọi trong `hash_password`
đúng ra **không bao giờ nổ** — nếu nổ thì là code mới quên validate, và nó nổ ở dev chứ không
âm thầm cho ra mật khẩu ngắn hơn người dùng tưởng.

> **Vì sao không để `max_length=72` cho gọn.** `security.py::_prepared` đang **cắt im lặng**
> ở byte thứ 72 ([security.py:23](../../apps/backend/app/core/security.py#L23)). Cắt im lặng
> nghĩa là: đặt mật khẩu 80 byte, hệ thống chỉ lưu 72 byte đầu, người dùng gõ đúng 72 byte đầu
> **cũng đăng nhập được** — mật khẩu ngắn hơn họ tưởng mà không ai báo. Từ chối thẳng thì
> người dùng biết mà đổi. **KHÔNG đổi sang Argon2id** chỉ vì việc này: phải xử lý hash cũ +
> thêm dependency, trong khi bcrypt vẫn là lựa chọn hợp lệ và lỗ hổng thật chỉ là chỗ cắt im
> lặng.
>
> *Ghi chú lệch chuẩn có sẵn*: `UserCreate` để `min_length=6`, `RegisterRequest` đặt
> `min_length=8`. Cố ý để lệch (admin tạo hộ thì tự chịu trách nhiệm), không phải quên.

Xử lý:

1. Email được chuẩn hoá về chữ thường — **không làm ở đây**, làm trong tầng repo, xem §4.4.
2. `create_user(email, name, role="user", password_hash=hash_password(...))`.
   **`role` hardcode trong handler, TUYỆT ĐỐI không đọc từ body** — nhận role từ client là mở
   đường tự phong admin. (Đây là khác biệt duy nhất về bản chất so với `POST /api/admin/users`,
   nơi role đến từ body nhưng đã có `require_admin` chắn.)
3. Trùng email → bắt `psycopg.errors.UniqueViolation` (đã có `UNIQUE` ở
   [db.py:42](../../apps/backend/app/core/db.py#L42)) → `AppError(409, "email_taken",
   "Email này đã được đăng ký.")`. Dùng chính pattern của
   [users.py:50](../../apps/backend/app/api/users.py#L50).
4. Trả **`LoginResponse`** (`201`) — cấp luôn `create_access_token` → frontend auto-login,
   không bắt người dùng gõ lại mật khẩu vừa đặt.

> **Quota cho người tự đăng ký.** `question_quota` mặc định `NULL` = **không giới hạn**
> ([db.py:47](../../apps/backend/app/core/db.py#L47)). Với đăng ký mở, nên đặt một trần mặc
> định (ví dụ 30 câu/ngày) cho tài khoản tự đăng ký; admin vẫn nới được từng người ở
> `/admin/users`. Sửa 1 dòng: thêm tham số `question_quota` vào `create_user`. **Đây là đề
> xuất, chưa chốt** — nếu chỉ demo nội bộ thì cứ để `NULL`.

### 4.3 Đăng nhập Google

#### 4.3.1 Việc trên Google Cloud Console (user tự làm, ~15 phút)

Dùng **cùng project đang cấp `GOOGLE_MAPS_API_KEY`** cho gọn.

1. *APIs & Services → OAuth consent screen*: User Type **External**, điền tên app + email hỗ
   trợ. Scope để nguyên mặc định (`openid`, `email`, `profile` — **non-sensitive**, nên
   **không phải qua review verification của Google**; có thể Publish thẳng sang Production).
   Nếu để **Testing** thì phải thêm từng email vào danh sách Test users mới đăng nhập được.
2. *Credentials → Create Credentials → OAuth client ID → Web application*.
   - **Authorized JavaScript origins**: `http://localhost:5173` (thêm domain thật khi deploy).
   - **Authorized redirect URIs**: **để trống** — luồng ID token không redirect.
3. Copy **Client ID** (dạng `xxx.apps.googleusercontent.com`). **Client secret không dùng đến.**
4. Vào root `.env` thêm:
   ```
   GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
   ```
   và `apps/frontend/.env` thêm `VITE_GOOGLE_CLIENT_ID=` (cùng giá trị — Client ID là public,
   lộ ra bundle là bình thường, bảo mật nằm ở origin allowlist + chữ ký của Google).

#### 4.3.2 Schema DB

Hai lệnh `ALTER` idempotent nối vào `SCHEMA_STATEMENTS` (đúng pattern
[db.py:55-56](../../apps/backend/app/core/db.py#L55-L56) — **dùng ALTER chứ không drop+recreate**
vì `users` đã có dữ liệu dev thật và bị `conversations` tham chiếu):

```sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS google_sub TEXT UNIQUE;
ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL;
```

- **`google_sub` là khoá định danh thật, KHÔNG phải email.** Google nói rõ: chỉ `sub` mới
  bất biến; email đổi được. Email chỉ dùng để **phát hiện tài khoản đã tồn tại** (→ `409`);
  **tuyệt đối không dùng để tự động liên kết** — xem §4.3.3.
- `password_hash` nullable → tài khoản Google-only không có mật khẩu. Kéo theo:
  - `User.password_hash: str | None`.
  - `verify_password(password, password_hash: str | None) -> bool`: `None` → `False`
    (hàm hiện đã nuốt `ValueError` cho hash rỗng/sai định dạng, chỉ cần thêm nhánh `None`).
  - `login()` do đó tự động từ chối tài khoản Google-only bằng đúng message
    `invalid_credentials` — không lộ "tài khoản này đăng nhập bằng Google".

#### 4.3.3 `POST /api/auth/google`

```python
# body: {"credential": "<JWT Google trả về cho nút Sign in with Google>"}
import cachecontrol, requests
from google.auth.transport import requests as ga_requests
from google.oauth2 import id_token

# google-auth KHÔNG tự cache cert: docs ghi "By default, this will re-fetch certificates for
# each verification". Tái dùng Request() chỉ tái dùng TCP connection. Muốn cache thật phải bọc
# session bằng CacheControl (đọc header Cache-Control của Google).
_GA_REQUEST = ga_requests.Request(session=cachecontrol.CacheControl(requests.Session()))

def _verify(credential: str) -> dict:
    return id_token.verify_oauth2_token(
        credential, _GA_REQUEST, get_settings().google_client_id
    )
```

`verify_oauth2_token` tự kiểm **chữ ký, `aud`, `exp`, `iss`**. Phân biệt **3 loại lỗi**, đừng
gộp làm một:

| Lỗi | Nguyên nhân | Trả về |
|---|---|---|
| `ValueError` | Token sai/hết hạn/`aud` không khớp | `401 invalid_google_token` |
| `GoogleAuthError` | `iss` không phải Google | `401 invalid_google_token` |
| `TransportError` | Không tải được cert của Google (mạng/Google sập) | `503 google_unavailable` |
| `settings.google_client_id` rỗng | Chưa cấu hình Console | `503 google_login_disabled` |

```python
from google.auth.exceptions import GoogleAuthError, TransportError

try:
    idinfo = await anyio.to_thread.run_sync(_verify, body.credential)
except TransportError:                      # PHẢI đứng trước
    raise AppError(503, "google_unavailable",
                   "Google tạm thời không phản hồi. Vui lòng thử lại.")
except (ValueError, GoogleAuthError):
    raise AppError(401, "invalid_google_token",
                   "Thông tin đăng nhập Google không hợp lệ.")
```

**Thứ tự `except` không được đảo**: `TransportError` **kế thừa** `GoogleAuthError`
(`Exception → GoogleAuthError → TransportError`). Đặt `GoogleAuthError` lên trước là nuốt luôn
lỗi mạng → **Google sập bị báo thành "token không hợp lệ"**, tức đổ lỗi cho người dùng vì sự
cố phía Google. Còn nếu chỉ `except ValueError` như bản plan đầu thì cả `GoogleAuthError` lẫn
`TransportError` đều lọt ra ngoài thành **500 trần**.

Kiểm thêm: `idinfo.get("email_verified") is not True` → `401 google_email_unverified`. Gọi
`_verify` trong `anyio.to_thread.run_sync` (phát HTTP lấy cert → blocking).

**Thứ tự tra người dùng — KHÔNG tự động ghép tài khoản** (sửa 2026-07-30, xem hộp dưới):

1. `get_user_by_google_sub(sub)` → có thì đăng nhập luôn.
2. Chưa có → `get_user_by_email(email)`:
   - **Có** → **DỪNG, trả `409 account_link_required`**: *"Email này đã đăng ký bằng mật khẩu.
     Hãy đăng nhập bằng mật khẩu."* KHÔNG ghi `google_sub`, KHÔNG cấp token.
   - Không → **tạo mới**: `role="user"`, `password_hash=NULL`, `google_sub=sub`,
     `name = idinfo.get("name") or email.split("@")[0]`.
3. `is_active=False` → `403 account_locked` (giống `login`, đừng bỏ sót nhánh này — nếu quên,
   tài khoản bị admin khóa vẫn vào được bằng cửa Google).
4. Trả `LoginResponse` **y hệt** `/login`.
5. **Race**: hai request Google đầu tiên của cùng một `sub` có thể cùng qua bước 1 rồi cùng
   INSERT → bắt `UniqueViolation` trên `google_sub` và **đọc lại user** thay vì trả 500.

> **⚠️ Vì sao bỏ auto-link (bản plan đầu SAI).** Bản đầu cho ghép khi `email_verified=true`,
> lập luận "Google đã xác minh email". Cờ đó chỉ chứng minh **Google** tin email, KHÔNG chứng
> minh tài khoản local cùng email là của cùng một người — mà `/register` thì **mở và không
> xác minh email**. Kịch bản chiếm tài khoản (pre-hijacking):
> 1. Kẻ xấu đăng ký trước bằng email nạn nhân, đặt mật khẩu của nó.
> 2. Nạn nhân bấm "Đăng nhập với Google" → hệ thống ghép Google vào chính tài khoản đó.
> 3. Nạn nhân dùng bình thường, không biết gì. Kẻ xấu **vẫn đăng nhập được bằng mật khẩu cũ**
>    và đọc toàn bộ hội thoại của nạn nhân.
>
> Google cũng nói rõ `email_verified=true` **chưa đủ** để coi Google là bên có thẩm quyền với
> email thuộc domain bên thứ ba — chỉ Gmail hoặc Workspace (có claim `hd`) mới chắc chắn.
>
> **Liên kết Google vào tài khoản có sẵn = NỢ, không làm ở MVP.** Đường đúng: người dùng đăng
> nhập bằng mật khẩu trước (chứng minh sở hữu tài khoản), rồi mới bấm "Liên kết Google" trong
> trang cá nhân — mà trang cá nhân thì **hiện chưa có**.

### 4.4 Chuẩn hoá email — quy hết về chữ thường (chốt 2026-07-30)

```python
# app/models/user.py
def normalize_email(raw: str) -> str:
    return raw.strip().lower()
```

**Áp NGAY TRONG tầng repo**, không phải ở từng handler:

```python
def get_user_by_email(email: str) -> User | None:
    ... WHERE email = %s", (normalize_email(email),)

def create_user(email: str, ...) -> User:
    ... VALUES (%s, ...)", (normalize_email(email), ...)
```

Vì sao đặt ở repo chứ không ở API: có **5 cửa** cùng chạm email (`/login`, `/register`,
`/google`, `POST /api/admin/users`, và mọi chỗ gọi `get_user_by_email`). Bắt mỗi handler tự
nhớ gọi `normalize_email` là **sót một chỗ là hở lại** — mà hở ở đây không phải lỗi nhỏ, xem
bảng dưới. Đặt ở repo thì mọi đường vào đều đi qua, kể cả code viết sau này.

**Tiện thể sửa luôn bug hiện có**: [auth.py:28](../../apps/backend/app/api/auth.py#L28) đang
tra email nguyên văn. Nếu chỉ `/register` hạ chữ thường mà `/login` thì không, người đăng ký
`Long@Gmail.com` sẽ **không bao giờ đăng nhập lại được** (DB lưu `long@…`, truy vấn tìm
`Long@…`). Chuẩn hoá ở repo làm `/login` hết lỗi mà không phải sửa `api/auth.py`.

| Nếu KHÔNG chuẩn hoá | Hậu quả |
|---|---|
| Đăng ký `Long@Gmail.com`, đăng nhập gõ `long@gmail.com` | 401 dù mật khẩu đúng |
| Đăng ký 2 lần khác kiểu chữ | `TEXT UNIQUE` so byte nên **không chặn** → 2 tài khoản 1 người |
| Đăng nhập Google | Google trả email theo dạng chuẩn của Google, không phải dạng người dùng gõ → tra không thấy → **tạo tài khoản thứ hai** cho cùng một Gmail |

**Cơ sở**: RFC 5321 §2.4 cho phép local-part phân biệt hoa thường, nhưng chính RFC đó ghi
*"Exploiting the case sensitivity of mailbox local-parts impedes interoperability and is
discouraged"*. Gmail/Workspace/Outlook/Yahoo đều không phân biệt → với tập người dùng của đồ
án, `A@gmail.com` và `a@gmail.com` là **cùng một hòm thư**, tách thành 2 tài khoản không bảo
vệ được ai.

**Cố ý KHÔNG làm**: bỏ dấu chấm và phần `+tag` (`l.o.n.g+test@gmail.com` → `long@gmail.com`).
Đó là luật riêng của Gmail; áp cho domain khác sẽ gộp nhầm hai người thật sự khác nhau.
Chuẩn hoá chỉ đụng phần mọi nhà cung cấp đều đồng ý: cắt khoảng trắng + hạ chữ thường.

**Dữ liệu sẵn có: không phải dọn.** Đã kiểm tra 2026-07-30, bảng `users` chỉ có
`admin@example.com` và `user@example.com`, đều đã là chữ thường → không có cặp trùng kiểu
`A@x.com`/`a@x.com` cần gộp trước khi siết ràng buộc.

### 4.5 Test backend (`tests/test_auth.py`)

Đăng ký: thành công `201` + token dùng được ngay ở `/me`; trùng email `409 email_taken`; mật
khẩu < 8 ký tự `422`; **mật khẩu 72 ký tự tiếng Việt có dấu (> 72 byte) → `422`**, không phải
âm thầm cắt; **gửi kèm `"role": "admin"` trong body vẫn ra `user`**.

Giới hạn bcrypt phải test **cả cửa admin** (`tests/test_users.py`): `POST /api/admin/users`
với mật khẩu > 72 byte → `422`. Không có test này thì lần sau ai đó nới `max_length` ở
`UserCreate` là lỗ hổng quay lại mà không ai biết.

Chuẩn hoá email (§4.4) — 3 test, đây là phần dễ tưởng đã đúng mà thực ra chưa:
- đăng ký `A@X.com` rồi **đăng nhập bằng `a@x.com`** → 200 (bug `/login` cũ);
- đăng ký `A@X.com` rồi đăng ký `a@x.com` → `409 email_taken`;
- đăng ký `  a@x.com  ` (có khoảng trắng) → `/me` trả về đúng `a@x.com`.

Google: `monkeypatch` `app.api.auth.id_token.verify_oauth2_token` trả dict giả (KHÔNG gọi mạng
thật trong test) → tạo mới; đăng nhập lần 2 cùng `sub` ra cùng `user.id`; `verify` ném
`ValueError` → `401`; **ném `TransportError` → `503`** (không được thành 401 hay 500);
`email_verified=False` → `401`; user `is_active=False` → `403`.

**Test chốt lỗ hổng pre-hijacking (§4.3.3)** — quan trọng nhất trong nhóm này: tạo sẵn user
`nan-nhan@x.com` bằng `/register` (có mật khẩu), rồi gọi `/google` với `email` y hệt nhưng
`sub` mới → phải ra **`409 account_link_required`**, và kiểm tra thêm rằng
`google_sub` của user đó **vẫn là NULL** (không âm thầm ghép).

Fixture DB rollback sẵn có lo phần dọn dẹp.

## 5. Frontend

### 5.1 File mới / sửa

```
package.json                        + @react-oauth/google (PIN 0.13.5, không dùng ^)
.env / .env.example                 + VITE_GOOGLE_CLIENT_ID
src/api/client.ts                   SỬA BUG — 401 đang nuốt message backend (§5.1.1)
src/api/auth.ts                     + register(), loginWithGoogle(credential)
src/features/auth/AuthLayout.tsx    MỚI — tách bố cục 2 cột + ảnh bìa từ LoginPage
src/features/auth/RegisterForm.tsx  MỚI
src/features/auth/useRegister.ts    MỚI (soi gương useLogin)
src/features/auth/GoogleButton.tsx  MỚI — <GoogleLogin> + gọi loginWithGoogle
src/pages/RegisterPage.tsx          MỚI
src/pages/LandingPage.tsx           MỚI
src/pages/LoginPage.tsx             sửa: dùng AuthLayout + gắn GoogleButton + link "Đăng ký"
src/app/routes.tsx                  sửa cây route (§3)
useLogin/RoleGuard/AppSidebar       sửa "/" -> "/chat" (§3) + useLogin đọc state.from (§5.1.2)
```

**Tách `AuthLayout` trước, rồi mới viết RegisterPage** — nếu không sẽ copy-paste 40 dòng bố cục
2 cột của `LoginPage` sang trang thứ hai, và lần sửa ảnh bìa tiếp theo phải sửa hai chỗ.

#### 5.1.1 Bug đang chạy: `client.ts` nuốt mọi lỗi 401

[client.ts:62-65](../../apps/frontend/src/api/client.ts#L62-L65) chặn **mọi** response 401,
xoá session và ném `ApiError(401, "unauthorized", "Phiên đăng nhập đã hết hạn.")` — **trước
khi** đọc body `{code, message}` của backend. Hậu quả **ngay hôm nay, chưa cần tới đăng ký**:
gõ sai mật khẩu ở màn đăng nhập hiện ra *"Phiên đăng nhập đã hết hạn"* thay vì *"Email hoặc
mật khẩu không đúng"*. Comment ở [useLogin.ts:22](../../apps/frontend/src/features/auth/useLogin.ts#L22)
("Backend trả message tiếng Việt sẵn") đang **mô tả sai** hành vi thật. `account_locked` hiện
đúng chỉ vì nó là 403, đi nhánh `parseError`.

**Phạm vi chính xác: CHỈ lỗi 401.** Các lỗi khác đi nhánh `parseError` và hiện đúng —
`account_locked` (403), `email_taken` (409), `account_link_required` (409),
`google_unavailable` (503) đều không bị ảnh hưởng. Danh sách bị nuốt:

| Code | Endpoint | Đáng lẽ phải hiện |
|---|---|---|
| `invalid_credentials` | `/login` | "Email hoặc mật khẩu không đúng." |
| `invalid_google_token` | `/google` | "Thông tin đăng nhập Google không hợp lệ." |
| `google_email_unverified` | `/google` | "Email Google chưa được xác minh." |

**Sửa**: chỉ coi 401 là "hết phiên" khi request **có gắn token** và **không phải endpoint
auth**. Ba endpoint `/api/auth/login|register|google` luôn giữ nguyên `code`/`message` của
backend:

```ts
const AUTH_PATHS = ["/api/auth/login", "/api/auth/register", "/api/auth/google"];
const isAuthEndpoint = AUTH_PATHS.some((p) => path.startsWith(p));

if (res.status === 401 && token && !isAuthEndpoint) {
  useAuthStore.getState().clear();          // phiên hết hạn thật -> RequireAuth đá về /login
  throw new ApiError(401, "unauthorized", "Phiên đăng nhập đã hết hạn.");
}
// còn lại rơi xuống nhánh !res.ok -> parseError giữ nguyên code/message backend
```

Điều kiện `token &&` quan trọng không kém: chưa đăng nhập mà gọi API thì `clear()` là vô
nghĩa, và nó xoá luôn cơ hội hiện message thật.

#### 5.1.2 `state.from` hiện chưa ai đọc

[RequireAuth.tsx:9](../../apps/frontend/src/features/auth/RequireAuth.tsx#L9) có lưu
`state.from`, nhưng [useLogin.ts:20](../../apps/frontend/src/features/auth/useLogin.ts#L20)
`navigate("/")` cứng — nên nó **chưa từng hoạt động** (bản plan đầu ghi "vẫn hoạt động" là
sai). Nhân lúc đổi `/` → `/chat` thì đọc luôn:
`navigate(location.state?.from ?? "/chat", { replace: true })`. Áp cho cả `useRegister` và
đường Google.

### 5.2 Nút Google

Dùng `@react-oauth/google` — **wrapper CỘNG ĐỒNG** (tác giả MomenSherif) quanh SDK Google
Identity Services, **không phải thư viện chính thức của Google**. Vẫn dùng vì nó mỏng và còn
được maintain (0.13.5), nhưng vì là bên thứ ba nên **pin version cứng** (`"0.13.5"`, không
`^`) — nó nằm ngay trên đường đăng nhập, một bản minor lỗi là chặn cửa vào hệ thống. Không tự
nhúng `<script src="accounts.google.com/gsi/client">` bằng tay.

```tsx
// Bọc CHỈ ở trang auth, không bọc toàn app: provider nạp script GIS khi mount,
// trang chat/admin không cần tới.
<GoogleOAuthProvider clientId={import.meta.env.VITE_GOOGLE_CLIENT_ID}>
  <GoogleLogin
    onSuccess={(res) => submitGoogle(res.credential!)}  // credential = ID token
    onError={() => setError("Không đăng nhập được bằng Google.")}
    locale="vi"
    width="320"   // CHUỖI pixel, tối đa "400" — không phải số, không phải "100%"
  />
</GoogleOAuthProvider>
```

`width` theo hợp đồng GIS là **`string` chứa số pixel**, tối đa `"400"` — tài liệu ghi rõ kiểu
`string` và ví dụ `width: "400"`. Truyền số (`width={320}`) là **sai kiểu, TypeScript báo lỗi**;
truyền `"100%"` thì sai đơn vị. Muốn nút co giãn theo cột thì bọc div canh bằng CSS — cỡ nút do
Google render, không phải do mình.

`submitGoogle` → `loginWithGoogle(credential)` → `setAuth(...)` → `navigate("/chat")` — dùng
lại nguyên đường của `useLogin`, chỉ khác hàm API. Đặt nút ở **cả** `/login` và `/register`
(cùng một nút, cùng một endpoint — người dùng lần đầu thì backend tự tạo tài khoản; không cần
phân biệt "đăng ký bằng Google" với "đăng nhập bằng Google").

`VITE_GOOGLE_CLIENT_ID` rỗng → **không render nút** (đừng để nút chết trên màn hình lúc chưa
cấu hình Console).

### 5.3 Landing page

Một trang tĩnh, **không thêm dependency nào**, dùng lại token màu sẵn có (brand `#A4161A`, nền
kem, serif+sans) và ảnh `src/assets/login-hero.jpg`.

Bố cục đề xuất, trên xuống dưới:

1. **Header dính**: logo "LS" + tên app; bên phải `Đăng nhập` / `Đăng ký` — hoặc nút **"Vào hỏi
   đáp"** nếu `authStore.token` đã có.
2. **Hero**: tiêu đề + một câu tagline ("Hỏi đáp lịch sử Việt Nam có căn cứ từ tài liệu, hiển
   thị trên bản đồ và dòng thời gian") + 2 nút CTA + ảnh bìa.
3. **3 thẻ tính năng**: (a) câu trả lời trích dẫn nguồn, click xem toàn văn; (b) sự kiện lên
   bản đồ + timeline, có trình chiếu; (c) RAG + GraphRAG + hybrid retrieval.
4. **Phạm vi dữ liệu**: nói thật — giai đoạn Pháp thuộc → thống nhất đất nước, nguồn là SGK/
   tài liệu đã số hoá; hệ thống trả "chưa đủ thông tin" thay vì đoán. (Đúng tinh thần honest
   behavior của đồ án; đồng thời chặn kỳ vọng sai.)
5. **Dành cho ai**: giáo viên lịch sử — soạn bài, tra cứu mốc sự kiện, chiếu bản đồ trên lớp.
6. **Footer**: "Đồ án tốt nghiệp · Agentic RAG cho lịch sử Việt Nam".

Ảnh chụp màn hình thật (chat + bản đồ) sẽ thuyết phục hơn nhiều so với mô tả chữ — chụp sau khi
route đã đổi xong, bỏ vào `src/assets/`.

### 5.4 Test frontend

- `routes.test.tsx`: chưa đăng nhập vào `/` thấy landing (KHÔNG bị đá sang `/login`); chưa đăng
  nhập vào `/chat` thì bị đá sang `/login`; đã đăng nhập vào `/login` thì sang `/chat`.
- `RegisterForm.test.tsx`: submit gọi API đúng payload; lỗi 409 hiện message tiếng Việt.
- **`client.test.ts` (§5.1.1)**: 401 từ `/api/auth/login` **giữ nguyên** `code`/`message` của
  backend và **KHÔNG** gọi `authStore.clear()`; 401 từ endpoint thường khi đang có token thì
  ngược lại. Đây là test chốt bug, không có nó thì lần refactor sau dễ nuốt lại.
- **Mock `@react-oauth/google`** trong test setup — SDK Google không chạy được trong jsdom.

## 6. Thứ tự làm

| Pha | Nội dung | Verify xong pha |
|---|---|---|
| **A** | Đăng ký thường (BE §4.2 + **chuẩn hoá email §4.4** + FE `AuthLayout`/`RegisterForm`/`RegisterPage` + route `/register`) | Đăng ký tài khoản mới ở UI → vào thẳng khu hỏi đáp; email trùng báo lỗi tiếng Việt; đăng ký `A@X.com` rồi đăng nhập `a@x.com` vẫn vào được |
| **B** | Landing + đổi cây route (§3 + §5.3) | Ẩn danh vào `/` thấy landing; `/chat` vẫn gác; sidebar + mọi redirect trỏ đúng |
| **C** | Google Sign-In (Console §4.3.1 → DB §4.3.2 → API §4.3.3 → nút §5.2) | Email mới → tạo user mới; email đã đăng ký bằng mật khẩu → **409, KHÔNG ghép** |

Ba pha độc lập, mỗi pha tự chạy được — **đừng gộp**. Pha B chạm nhiều file nhất nhưng toàn sửa
một dòng; pha C là pha duy nhất phụ thuộc thao tác ngoài repo (Console).

### Đã làm gì (2026-07-30) — A ✅, C ✅, B ⏸️

Pha A + C code xong; **pha B hoãn theo yêu cầu user** nên §3 (đổi cây route) và §5.3
(landing) **chưa động tới**. Hệ quả cần nhớ:

- `/` **vẫn là `AskPage`** sau `RequireAuth` — không có route `/chat`, không sửa
  `RoleGuard`/`AppSidebar`. Bảng §3 giữ nguyên làm việc-phải-làm khi quay lại pha B.
- Sau đăng nhập/đăng ký/Google đều về `redirectTargetFrom(location.state)`, mặc định `"/"`.
  Khi làm pha B chỉ cần đổi hằng `DEFAULT_AFTER_AUTH` trong
  [redirectTarget.ts](../../apps/frontend/src/features/auth/redirectTarget.ts) — logic
  `state.from` (§5.1.2) **đã nối xong** cho cả 3 đường vào.

Ba chỗ **lệch có chủ ý** so với chữ trong plan:

| Plan viết | Thực tế | Lý do |
|---|---|---|
| `<GoogleLogin locale="vi">` | `<GoogleOAuthProvider locale="vi">` | Ở `@react-oauth/google@0.13.5`, `locale` thuộc **provider** (nó nạp script GIS kèm `hl`); đặt trên `GoogleLogin` là **TS2322** |
| `onSuccess={(res) => submitGoogle(res.credential!)}` | thiếu `credential` → hiện lỗi | `!` biến trường hợp bất thường thành **bấm-mà-không-gì-xảy-ra** |
| `question_quota` mặc định cho người tự đăng ký | **để `NULL`** (không giới hạn) | §4.2 ghi rõ "đề xuất, chưa chốt"; hiện chỉ demo nội bộ. Muốn siết thì thêm tham số `question_quota` vào `create_user` |

Còn nợ ngoài repo: **§4.3.1 (Google Cloud Console)** — chưa ai bấm. Chừng nào
`GOOGLE_CLIENT_ID` / `VITE_GOOGLE_CLIENT_ID` còn rỗng thì backend trả `503
google_login_disabled` và frontend **không render nút** (cố ý, không phải lỗi).

**Sửa `client.ts` (§5.1.1) làm NGAY đầu pha A**, trước cả `RegisterForm`: nó là bug đang chạy,
và mọi message lỗi của `/register`, `/google` sau này đều đi qua chỗ đó. Sửa sau thì suốt pha
A lẫn pha C mình sẽ debug nhầm — tưởng backend trả sai `code`, hoá ra frontend nuốt mất.

## 6b. Rate limit — ⏸️ HOÃN (chốt 2026-07-30), KHÔNG làm trong pha A/B/C

> **Quyết định user 2026-07-30**: để sau, không nằm trong 3 pha của plan này. Mục này giữ
> nguyên làm bản thiết kế sẵn cho lúc quay lại — **đừng xoá**.
>
> **Điều kiện bắt buộc quay lại**: trước khi mở hệ thống ra ngoài localhost. Chừng nào còn
> chạy máy cá nhân để demo/chấm đồ án thì thiếu rate limit **không ảnh hưởng gì** — không có
> ai lạ gọi tới được. Đã ghi vào `CLAUDE.md` mục "⚠️ Còn lại trước khi deploy thật" (3).
>
> **Cái đang chấp nhận trong lúc hoãn**: (1) `/login` không giới hạn số lần thử → brute-force
> mật khẩu thoải mái; (2) quota tính theo tài khoản mà đăng ký lại mở → tạo thêm tài khoản là
> vượt quota, đốt API cost thật.

Quota hiện tính **theo tài khoản** ([db.py:47](../../apps/backend/app/core/db.py#L47)), mà
đăng ký lại mở → ai muốn vượt quota chỉ cần tạo thêm tài khoản. Ngoài ra `/login` không giới
hạn số lần thử = mời brute-force.

Chia theo mức độ, **làm tới đâu tuỳ nơi deploy**:

| Mức | Việc | Khi nào cần |
|---|---|---|
| 1 | **Rate limit `/login` theo IP + email** | Nên làm ngay cả khi chỉ demo — chặn brute-force, rẻ |
| 2 | Rate limit `/register` + `/google` theo IP | Khi mở ra ngoài localhost |
| 3 | Quota tổng theo IP (không chỉ theo tài khoản) | Khi mở ra ngoài localhost |
| 4 | Invite code **hoặc** email verification | Khi deploy công khai thật và LLM tốn tiền thật |

**Khi quay lại thì làm mức 1 trước** (in-process counter là đủ — backend chạy 1 worker; muốn
chuẩn hơn thì Redis đã có sẵn trong stack nhưng backend **chưa** nối Redis, thêm là thêm
dependency mới). Mức 2–3 khi có domain thật. Mức 4 chọn **invite code** nếu chỉ mở cho một
nhóm giáo viên — rẻ hơn hẳn email verification (không cần SMTP).

**Ghi chú kỹ thuật để khỏi tra lại**: `slowapi` (thư viện mặc định cho FastAPI) **không keyed
theo email được** — `key_func` của nó là hàm **sync nhận `Request`**, chạy ở tầng decorator
nơi body chưa đọc được, trong khi email nằm trong body. Nên phần theo email vẫn phải tự viết.
Ước lượng: `app/core/rate_limit.py` ~40 dòng (cửa sổ trượt, `check()`/`record()`/`reset()`
tách riêng) + ~6 dòng ghép vào `login()` + 4 test.

Bốn điểm dễ làm sai, ghi sẵn:
1. **Key theo email chỉ đếm lần THẤT BẠI** và **reset khi đăng nhập đúng**; key theo IP mới
   đếm mọi request. Đếm mọi request theo email là chặn oan người dùng nhiều thiết bị.
2. **Không khoá vĩnh viễn theo email** — cửa sổ phải tự hết hạn, nếu không thì ai cũng khoá
   được tài khoản người khác chỉ bằng cách gõ sai vài lần (biến chống tấn công thành tấn công).
3. **429 phải giống hệt nhau** cho email có thật và không tồn tại, nếu không nó thành công cụ
   dò email đã đăng ký — phá đúng thứ [auth.py:29](../../apps/backend/app/api/auth.py#L29)
   đang cố giữ.
4. **IP sau proxy**: `request.client.host` trả IP proxy → cả hệ thống dùng chung một quota,
   một người spam là khoá tất cả. Cần `--proxy-headers --forwarded-allow-ips=<ip proxy>` và
   chỉ tin `X-Forwarded-For` từ proxy của mình. Repo **hiện chưa có gì** về việc này.

**Đừng làm CAPTCHA sớm**: nó đánh đổi trải nghiệm thật để đổi lấy rủi ro giả định, trong khi
mức 1–3 đã chặn được phần lớn.

## 7. Cố ý KHÔNG làm

- **Liên kết Google vào tài khoản mật khẩu có sẵn** (§4.3.3): cần trang cá nhân + luồng xác
  minh 2 bước, mà trang cá nhân chưa có. MVP trả `409 account_link_required`.
- **Quên mật khẩu / gửi email xác minh**: cần SMTP + template + token hết hạn. Ngoài phạm vi;
  admin đổi mật khẩu hộ được ở `/admin/users` nếu cần.
- **Refresh token / "ghi nhớ đăng nhập"**: JWT 60 phút, hết hạn thì đăng nhập lại — giữ nguyên
  quyết định của `backend-plan.md`.
- **Đổi JWT từ localStorage sang cookie HttpOnly**: cookie an toàn hơn trước XSS, nhưng đổi thì
  kéo theo CORS `credentials`, CSRF token, và sửa cả đường SSE `/ask` (đang tự gắn Bearer bằng
  `fetch`). **Ghi nhận là security debt**, không phải "đã cân nhắc và thấy ổn" — xem
  [authStore.ts:29](../../apps/frontend/src/store/authStore.ts#L29).
- **Facebook/GitHub login**: thêm provider nào cũng lặp lại y hệt §4.3, không có gì mới để học.
- **Đổi bcrypt → Argon2id**: xem hộp ở §4.2 — lỗ hổng thật là chỗ cắt im lặng, không phải thuật
  toán.

## 8. Rủi ro & bẫy

| Bẫy | Hậu quả nếu quên | Xử lý |
|---|---|---|
| `password_hash NOT NULL` chưa nới | `INSERT` user Google fail ở dòng đầu tiên | Chạy `init_db.py` (đã thêm ALTER) **trước** khi test pha C |
| Nhánh `is_active` ở `/google` | Tài khoản bị khóa vẫn vào được bằng cửa Google | Check `is_active` ở **cả hai** endpoint, như `login` đã làm |
| `role` đọc từ body `/register` | Người ngoài tự phong admin | Hardcode `"user"` trong handler |
| Đăng ký mở, quota `NULL` | Người lạ đốt API cost thật của đồ án | §4.2 — đặt quota mặc định, hoặc theo dõi ở `/admin/cost` |
| Origin `localhost:5173` chưa khai ở Console | Nút Google im lặng không hiện / console báo `origin_mismatch` | Khai origin **trước**, và khai lại khi deploy đổi domain |
| Consent screen để **Testing** | Chỉ email trong Test users đăng nhập được | Publish sang Production (không cần review với scope `email`/`profile`) |
| **Tự động ghép Google theo email** | **Kẻ đăng ký trước bằng email nạn nhân giữ được quyền đọc dữ liệu nạn nhân** | KHÔNG ghép, trả `409` (§4.3.3) — `email_verified` KHÔNG đủ để coi là cùng người |
| Bắt thiếu, hoặc đảo thứ tự `except` của google-auth | `TransportError` là subclass của `GoogleAuthError` → đặt sai thứ tự là Google sập bị báo "token không hợp lệ"; bắt thiếu là 500 trần | `TransportError` trước → `503`; rồi `(ValueError, GoogleAuthError)` → `401` (§4.3.3) |
| Test gọi `verify_oauth2_token` thật | Test phụ thuộc mạng, chạy CI là hỏng | `monkeypatch` (§4.5) |
| Chuẩn hoá email ở handler thay vì repo | Sót 1 trong 5 cửa là tài khoản nhân đôi / không đăng nhập lại được | Đặt trong `get_user_by_email`/`create_user` (§4.4) |
| Quên sửa `client.ts` trước | 3 lỗi **401** (`invalid_credentials`, `invalid_google_token`, `google_email_unverified`) hiện thành "Phiên đăng nhập đã hết hạn" → debug nhầm sang backend | Sửa đầu pha A (§5.1.1) |
| `max_length=72` cho mật khẩu | Đếm ký tự chứ không đếm byte → tiếng Việt có dấu bị bcrypt cắt im lặng | Validator đếm `len(v.encode("utf-8"))` (§4.2) |
| Chỉ validate byte ở `/register` | Cửa admin (`UserCreate`, đang `max_length=200`) vẫn cắt im lặng | Helper chung, gọi ở cả 3 chỗ kể cả `hash_password` (§4.2) |
| Tin `_GA_REQUEST` là đã cache cert | Mỗi lần đăng nhập Google là một round-trip tải cert | Bọc `CacheControl` (§4.3.3) |

**Nợ ghi sẵn**: tài khoản tạo bằng Google không có mật khẩu → sau này muốn cho họ đăng nhập
thường thì phải thêm luồng "đặt mật khẩu" trong trang cá nhân. Chưa cần cho MVP. Cùng chỗ đó
sẽ là nơi đặt luồng **liên kết Google** (§4.3.3) — hai việc này nên làm một lượt.

## 9. Liên quan

- [backend-plan.md](backend-plan.md) — kiến trúc auth/JWT gốc, phần "Sau MVP".
- [frontend-plan.md](frontend-plan.md) — cây route + quy ước feature folder.
- [activity-log-plan.md](activity-log-plan.md) — middleware tự ghi `/api/auth/*` vào
  `activity_log`, gồm cả 2 endpoint mới; không phải làm gì thêm.
