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

init_db()
