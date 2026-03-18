## Aladdin (MVP) — Django + HTMX

SaaS para restaurantes pequeños/medianos en LATAM: menú diario, pedidos, ventas a crédito, deudas y pagos.

### Stack
- **Backend**: Django 4.2
- **DB**: SQLite (modelado para migrar a PostgreSQL)
- **Frontend**: Django Templates + **HTMX**
- **Auth**: Django Auth (extensible)

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
- Login: **solo teléfono** (sin OTP). Teléfono permitido: `3117451274`.

### Rutas (MVP)
- `/` preauth por teléfono
- `/dashboard/` dashboard negocio (custom)
- `/accounts/login/` login
- `/menus/` menús por fecha
- `/orders/` pedidos
- `/credits/customers/` clientes + pagos
- `/m/<restaurant_uuid>/YYYY-MM-DD/` menú público para clientes (sin login)

