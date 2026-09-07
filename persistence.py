import os
import sqlite3
from datetime import datetime

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("SIAT_DB_PATH", os.path.join(APP_ROOT, "data", "siat_de.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS alertas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_estudiante TEXT NOT NULL UNIQUE,
    carrera TEXT,
    semestre TEXT,
    nivel_riesgo TEXT NOT NULL,
    probabilidad REAL NOT NULL,
    motivo TEXT,
    responsable TEXT,
    estado TEXT NOT NULL DEFAULT 'Pendiente',
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS intervenciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alerta_id INTEGER,
    codigo_estudiante TEXT NOT NULL,
    tipo TEXT NOT NULL,
    responsable TEXT NOT NULL,
    fecha_intervencion TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'Pendiente',
    resultado TEXT,
    observaciones TEXT,
    probabilidad_inicial REAL,
    nivel_riesgo_inicial TEXT,
    probabilidad_final REAL,
    nivel_riesgo_final TEXT,
    fecha_seguimiento TEXT,
    creado_en TEXT NOT NULL,
    actualizado_en TEXT NOT NULL,
    FOREIGN KEY (alerta_id) REFERENCES alertas(id)
);
CREATE INDEX IF NOT EXISTS idx_alertas_estado ON alertas(estado);
CREATE INDEX IF NOT EXISTS idx_alertas_riesgo ON alertas(nivel_riesgo);
CREATE INDEX IF NOT EXISTS idx_intervenciones_codigo ON intervenciones(codigo_estudiante);
CREATE INDEX IF NOT EXISTS idx_intervenciones_estado ON intervenciones(estado);
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario TEXT NOT NULL UNIQUE,
    nombre TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    rol TEXT NOT NULL DEFAULT 'Consulta',
    activo INTEGER NOT NULL DEFAULT 1,
    creado_en TEXT NOT NULL,
    actualizado_en TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS configuracion (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL,
    descripcion TEXT,
    actualizado_en TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS auditoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario TEXT NOT NULL,
    accion TEXT NOT NULL,
    modulo TEXT NOT NULL,
    detalle TEXT,
    fecha TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_auditoria_fecha ON auditoria(fecha);
"""

def connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con

def init_db():
    with connect() as con:
        con.executescript(SCHEMA)

def sync_alerts(records):
    """Crea alertas nuevas y refresca su riesgo sin borrar el seguimiento humano."""
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as con:
        for r in records:
            con.execute("""
                INSERT INTO alertas (
                    codigo_estudiante, carrera, semestre, nivel_riesgo, probabilidad,
                    motivo, responsable, estado, fecha_creacion, fecha_actualizacion
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Pendiente', ?, ?)
                ON CONFLICT(codigo_estudiante) DO UPDATE SET
                    carrera=excluded.carrera,
                    semestre=excluded.semestre,
                    nivel_riesgo=excluded.nivel_riesgo,
                    probabilidad=excluded.probabilidad,
                    motivo=excluded.motivo,
                    responsable=excluded.responsable,
                    fecha_actualizacion=excluded.fecha_actualizacion
            """, (
                str(r.get("codigo_estudiante", "")), str(r.get("carrera", "")),
                str(r.get("semestre", "")), str(r.get("nivel_riesgo", "")),
                float(r.get("probabilidad", 0)), str(r.get("motivo", "")),
                str(r.get("responsable", "")), now, now
            ))

def list_alerts(riesgo="", estado="", q=""):
    sql = "SELECT * FROM alertas WHERE 1=1"
    params = []
    if riesgo:
        sql += " AND nivel_riesgo = ?"; params.append(riesgo)
    if estado:
        sql += " AND estado = ?"; params.append(estado)
    if q:
        sql += " AND (codigo_estudiante LIKE ? OR carrera LIKE ? OR motivo LIKE ?)"
        term = f"%{q}%"; params.extend([term, term, term])
    sql += " ORDER BY probabilidad DESC, fecha_actualizacion DESC"
    with connect() as con:
        return [dict(r) for r in con.execute(sql, params).fetchall()]

def get_alert(alert_id):
    with connect() as con:
        row = con.execute("SELECT * FROM alertas WHERE id=?", (alert_id,)).fetchone()
        return dict(row) if row else None

def update_alert(alert_id, estado, responsable):
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as con:
        con.execute(
            "UPDATE alertas SET estado=?, responsable=?, fecha_actualizacion=? WHERE id=?",
            (estado, responsable, now, alert_id)
        )

def create_intervention(data):
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as con:
        cur = con.execute("""
            INSERT INTO intervenciones (
                alerta_id, codigo_estudiante, tipo, responsable, fecha_intervencion,
                estado, resultado, observaciones, probabilidad_inicial,
                nivel_riesgo_inicial, fecha_seguimiento, creado_en, actualizado_en
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get("alerta_id"), data["codigo_estudiante"], data["tipo"],
            data["responsable"], data["fecha_intervencion"], data.get("estado", "Pendiente"),
            data.get("resultado", ""), data.get("observaciones", ""),
            data.get("probabilidad_inicial"), data.get("nivel_riesgo_inicial"),
            data.get("fecha_seguimiento") or None, now, now
        ))
        if data.get("alerta_id"):
            con.execute(
                "UPDATE alertas SET estado='En proceso', responsable=?, fecha_actualizacion=? WHERE id=?",
                (data["responsable"], now, data["alerta_id"])
            )
        return cur.lastrowid

def list_interventions(estado="", tipo="", codigo=""):
    sql = """SELECT i.*, a.carrera, a.semestre
             FROM intervenciones i LEFT JOIN alertas a ON a.id=i.alerta_id WHERE 1=1"""
    params = []
    if estado:
        sql += " AND i.estado=?"; params.append(estado)
    if tipo:
        sql += " AND i.tipo=?"; params.append(tipo)
    if codigo:
        sql += " AND i.codigo_estudiante=?"; params.append(codigo)
    sql += " ORDER BY i.fecha_intervencion DESC, i.id DESC"
    with connect() as con:
        return [dict(r) for r in con.execute(sql, params).fetchall()]

def get_intervention(intervention_id):
    with connect() as con:
        row = con.execute("SELECT * FROM intervenciones WHERE id=?", (intervention_id,)).fetchone()
        return dict(row) if row else None

def update_intervention(intervention_id, data):
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as con:
        current = con.execute("SELECT * FROM intervenciones WHERE id=?", (intervention_id,)).fetchone()
        if not current:
            return False
        con.execute("""
            UPDATE intervenciones SET tipo=?, responsable=?, fecha_intervencion=?,
                estado=?, resultado=?, observaciones=?, probabilidad_final=?,
                nivel_riesgo_final=?, fecha_seguimiento=?, actualizado_en=?
            WHERE id=?
        """, (
            data["tipo"], data["responsable"], data["fecha_intervencion"],
            data["estado"], data.get("resultado", ""), data.get("observaciones", ""),
            data.get("probabilidad_final"), data.get("nivel_riesgo_final"),
            data.get("fecha_seguimiento") or None, now, intervention_id
        ))
        if current["alerta_id"]:
            alert_state = "Cerrada" if data["estado"] == "Finalizada" else "En proceso"
            con.execute(
                "UPDATE alertas SET estado=?, responsable=?, fecha_actualizacion=? WHERE id=?",
                (alert_state, data["responsable"], now, current["alerta_id"])
            )
        return True

def effectiveness_report():
    rows = list_interventions()
    for r in rows:
        initial = r.get("probabilidad_inicial")
        final = r.get("probabilidad_final")
        r["reduccion_probabilidad"] = (
            round((float(initial) - float(final)) * 100, 1)
            if initial is not None and final is not None else None
        )
        r["efectiva"] = (
            "Sí" if r["reduccion_probabilidad"] is not None and r["reduccion_probabilidad"] > 0
            else ("No" if r["reduccion_probabilidad"] is not None else "Sin evaluación")
        )
    return rows

def get_user_by_username(username):
    with connect() as con:
        row = con.execute("SELECT * FROM usuarios WHERE usuario=?", (username,)).fetchone()
        return dict(row) if row else None

def list_users():
    with connect() as con:
        return [dict(r) for r in con.execute(
            "SELECT id, usuario, nombre, rol, activo, creado_en, actualizado_en FROM usuarios ORDER BY nombre"
        ).fetchall()]

def create_user_account(username, name, password_hash, role="Consulta"):
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as con:
        con.execute("""INSERT INTO usuarios
            (usuario,nombre,password_hash,rol,activo,creado_en,actualizado_en)
            VALUES (?,?,?,?,1,?,?)""", (username, name, password_hash, role, now, now))

def update_user_account(user_id, name, role, active, password_hash=None):
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as con:
        if password_hash:
            con.execute("""UPDATE usuarios SET nombre=?,rol=?,activo=?,password_hash=?,actualizado_en=?
                           WHERE id=?""", (name, role, int(active), password_hash, now, user_id))
        else:
            con.execute("""UPDATE usuarios SET nombre=?,rol=?,activo=?,actualizado_en=?
                           WHERE id=?""", (name, role, int(active), now, user_id))

def ensure_admin(password_hash):
    if get_user_by_username("admin") is None:
        create_user_account("admin", "Administrador SIAT-DE", password_hash, "Administrador")

def get_settings():
    defaults = {"low_threshold": "0.25", "high_threshold": "0.37", "periodo_activo": "2025-I"}
    with connect() as con:
        rows = {r["clave"]: r["valor"] for r in con.execute("SELECT clave,valor FROM configuracion")}
    defaults.update(rows)
    return defaults

def save_setting(key, value, description=""):
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as con:
        con.execute("""INSERT INTO configuracion(clave,valor,descripcion,actualizado_en)
                       VALUES(?,?,?,?) ON CONFLICT(clave) DO UPDATE SET
                       valor=excluded.valor,descripcion=excluded.descripcion,
                       actualizado_en=excluded.actualizado_en""",
                    (key, str(value), description, now))

def log_audit(username, action, module, detail=""):
    with connect() as con:
        con.execute("INSERT INTO auditoria(usuario,accion,modulo,detalle,fecha) VALUES(?,?,?,?,?)",
                    (username, action, module, detail, datetime.now().isoformat(timespec="seconds")))

def list_audit(limit=100):
    with connect() as con:
        return [dict(r) for r in con.execute(
            "SELECT * FROM auditoria ORDER BY id DESC LIMIT ?", (int(limit),)
        ).fetchall()]

def notification_counts():
    today = datetime.now().strftime("%Y-%m-%d")
    with connect() as con:
        pending = con.execute("SELECT COUNT(*) FROM alertas WHERE estado='Pendiente'").fetchone()[0]
        overdue = con.execute("""SELECT COUNT(*) FROM intervenciones
            WHERE estado!='Finalizada' AND fecha_seguimiento IS NOT NULL AND fecha_seguimiento < ?""",
            (today,)).fetchone()[0]
    return {"alertas_pendientes": pending, "seguimientos_vencidos": overdue, "total": pending + overdue}

init_db()
