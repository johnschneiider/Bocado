## Bocado (Antes Aladdin) — Django + HTMX

Plataforma de pedidos de comida estilo **Didifood** (SaaS + Clientes).

### 🆕 Nuevas funcionalidades (Rebranding)

1. **Vista pública tipo Didifood**:
   - Home con grid de restaurantes
   - Cards de restaurantes con info básica
   - Vista detalle de restaurante con menús del día
   - Flujo de pedido intuitivo

2. **Navbar con dropdown de usuario**:
   - Icono de usuario con menú desplegable
   - Opción "Ver como cliente" / "Mi negocio"
   - Opción para registrarse como negocio

3. **Flujo de login**:
   - **Clientes**: Acceso directo a ver restaurantes (sin login requerido)
   - **Negocios**: Login con teléfono para acceder al dashboard

### Stack
- **Backend**: Django 4.2
- **DB**: PostgreSQL (production) / SQLite (development)
- **Frontend**: Django Templates + **HTMX**
- **Auth**: Django Auth (extensible)
- **Cache**: Django Cache (default: LocMemCache, configurable to Redis)
- **Rate Limiting**: Custom decorator for public endpoints

### Apps
- `accounts`: usuarios admin (SaaS admin / restaurant admin) + memberships
- `restaurants`: tenant `Restaurant` + `RestaurantLocation`
- `menus`: menú por fecha (`DailyMenu`) + ítems
- `orders`: pedidos + líneas
- `credits`: clientes (sin login) + deudas + pagos
- `dashboard`: KPIs básicos

### Tipos de “cuentas”
- **Negocio**: `restaurants.Restaurant` (tenant)
- **Cliente**: `credits.Customer` (no requiere login en MVP)
- **Mi administrador (SaaS)**: `accounts.UserProfile(role=SAAS_ADMIN)` sobre `auth.User`

### Estructura base de datos
- Entidades principales con **UUID** como PK.
- Todos los modelos incluyen `created_at` / `updated_at` vía `common.TimeStampedUUIDModel`.

### Setup (Windows / PowerShell)
Crear y usar el entorno virtual del proyecto:

```bash
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python manage.py migrate
```

Crear datos demo (restaurante, usuario admin, menú, pedidos, deuda y pago):

```bash
.\.venv\Scripts\python manage.py seed_demo
```

Iniciar servidor:

```bash
.\.venv\Scripts\python manage.py runserver
```

Luego abre:
- App: `http://127.0.0.1:8000/`
- Panel negocio (custom): `http://127.0.0.1:8000/dashboard/`

Credenciales demo:
- Usuario: `demo_admin`
- Login: **solo teléfono** (sin OTP). Puedes usar cualquier teléfono para login de admin.

### 🔧 Escalabilidad implementada

1. **🔒 Seguridad**
   - SECRET_KEY ahora está en variables de entorno (`.env`)
   - `DEBUG = False` en producción vía variable de entorno

2. **⚡ Performance**
   - Índices de base de datos en campos frecuentes (Order, Debt, etc.)
   - Cache en dashboard (5 minutos)
   - Rate limiting (30 req/min vista menú, 5 req/min creación pedido)

3. **🗄️ Database**
   - Soporte para PostgreSQL (production) y SQLite (dev)
   - Configuración vía `DATABASE_URL`

4. **🔍 Monitoreo**
   - Headers `X-RateLimit-*` en respuestas de rate limiting

### ⚠️ Notas de producción

1. Configura PostgreSQL:
   ```bash
   DATABASE_URL=postgres://user:password@localhost:5432/dbname
   ```

2. Para cache distribuido (opcional):
   ```bash
   REDIS_URL=redis://localhost:6379/0
   ```
   Y actualiza `config/settings.py` para usar Redis.

### Rutas

**Vistas Públicas (Clientes):**
- `/` Home con lista de restaurantes
- `/r/<restaurant_uuid>/` Detalle de restaurante y menús
- `/r/<restaurant_uuid>/order/` Hacer pedido en restaurante

**Vistas de Negocio (Admin):**
- `/dashboard/` Panel de control
- `/accounts/login/` Login para negocios
- `/menus/` Gestión de menús
- `/orders/` Gestión de pedidos
- `/credits/customers/` Gestión de clientes y créditos

**Vistas compatibles:**
- `/m/<restaurant_uuid>/YYYY-MM-DD/` Menú público antiguo

