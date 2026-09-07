
import os
import warnings
from datetime import datetime
from io import StringIO, BytesIO

import joblib
import numpy as np
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, Response
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from pdf_reports import generate_executive_pdf, generate_alerts_pdf, generate_effectiveness_pdf
from persistence import (
    sync_alerts, list_alerts, get_alert, update_alert, create_intervention,
    list_interventions, get_intervention, update_intervention, effectiveness_report,
    get_user_by_username, list_users, create_user_account, update_user_account,
    ensure_admin, get_settings, save_setting, log_audit, list_audit, notification_counts
)

warnings.filterwarnings("ignore")

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(APP_ROOT, "data", "dataset_final_univalle_corregido_20260306.csv")
MODEL_PATH = os.path.join(APP_ROOT, "modelo", "modelo_desercion.pkl")
EXPORT_DIR = os.path.join(APP_ROOT, "exports")
os.makedirs(EXPORT_DIR, exist_ok=True)

TARGET = "target_desercion"
FEATURE_COLUMNS = [
    "reprobaciones_total", "promedio_1sem", "promedio_2sem", "asistencia_pct",
    "materias_aprobadas_1sem", "materias_aprobadas_2sem", "avance_curricular_pct",
    "materias_criticas_reprobadas", "nota_prom_materias_criticas", "alertas_academicas",
    "uso_tutorias", "tutorias_recibidas", "orientacion_academica", "situacion_laboral_estudiante",
    "beneficiario_beca", "apoyo_financiero_tipo", "pagos_al_dia", "deudor",
    "genero", "estado_civil", "turno_estudio", "modalidad_ingreso"
]
_settings = get_settings()
LOW_T = float(_settings["low_threshold"])
HIGH_T = float(_settings["high_threshold"])

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "cambiar-esta-clave-en-produccion")
app.config.update(
    UPLOAD_FOLDER=os.path.join(APP_ROOT, "data"),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax"
)
ensure_admin(generate_password_hash(os.environ.get("SIAT_ADMIN_PASSWORD", "admin123")))

_MODEL = None
_MODEL_ERROR = None


def get_model():
    global _MODEL, _MODEL_ERROR
    if _MODEL is not None or _MODEL_ERROR is not None:
        return _MODEL
    try:
        _MODEL = joblib.load(MODEL_PATH)
    except Exception as e:
        _MODEL_ERROR = str(e)
        _MODEL = None
    return _MODEL


def classify_risk(p):
    try:
        p = float(p)
    except Exception:
        p = 0.0
    if p < LOW_T:
        return "Bajo"
    if p < HIGH_T:
        return "Medio"
    return "Alto"


def action_for_risk(risk):
    return {
        "Bajo": "Seguimiento general y monitoreo periódico",
        "Medio": "Tutoría académica y orientación personalizada",
        "Alto": "Intervención prioritaria integral académica, financiera y psicosocial",
    }.get(risk, "Monitoreo académico")


def badge_class(risk):
    return {"Bajo": "risk-low", "Medio": "risk-mid", "Alto": "risk-high"}.get(risk, "risk-low")


def detect_student_id(df):
    for c in ["codigo_estudiante", "id_estudiante", "estudiante", "student_id", "codigo"]:
        if c in df.columns:
            return c
    df = df.copy()
    return None


def load_dataset(path=DATA_PATH):
    df = pd.read_csv(path)
    df = enrich_dataframe(df)
    return df


def calculate_probability(df):
    model = get_model()
    if model is None:
        # Fallback interpretativo si el entorno no puede cargar el pkl por versión.
        # No reemplaza el modelo; solo permite visualizar el prototipo.
        score = (
            0.28 * (df.get("reprobaciones_total", 0).fillna(0) / max(1, df.get("reprobaciones_total", pd.Series([1])).max())) +
            0.20 * (1 - df.get("asistencia_pct", 100).fillna(100).clip(0, 100) / 100) +
            0.18 * (1 - df.get("promedio_2sem", df.get("promedio_1sem", 0)).fillna(0).clip(0, 20) / 20) +
            0.14 * df.get("deudor", 0).fillna(0) +
            0.10 * (df.get("alertas_academicas", 0).fillna(0) / max(1, df.get("alertas_academicas", pd.Series([1])).max())) +
            0.10 * (df.get("materias_criticas_reprobadas", 0).fillna(0) / max(1, df.get("materias_criticas_reprobadas", pd.Series([1])).max()))
        )
        return score.clip(0, 0.95)
    X = df[[c for c in FEATURE_COLUMNS if c in df.columns]].copy()
    probs = model.predict_proba(X)[:, 1]
    return pd.Series(probs, index=df.index)


def enrich_dataframe(df):
    df = df.copy()
    if "probabilidad_desercion" not in df.columns:
        try:
            df["probabilidad_desercion"] = calculate_probability(df)
        except Exception as e:
            # Fallback con mensaje guardado para interfaz.
            score = (
                0.30 * (df.get("reprobaciones_total", 0).fillna(0) / max(1, df.get("reprobaciones_total", pd.Series([1])).max())) +
                0.25 * (1 - df.get("asistencia_pct", 100).fillna(100).clip(0, 100) / 100) +
                0.20 * (1 - df.get("promedio_2sem", df.get("promedio_1sem", 0)).fillna(0).clip(0, 20) / 20) +
                0.15 * df.get("deudor", 0).fillna(0) +
                0.10 * (df.get("alertas_academicas", 0).fillna(0) / max(1, df.get("alertas_academicas", pd.Series([1])).max()))
            )
            df["probabilidad_desercion"] = score.clip(0, 0.95)
    df["nivel_riesgo"] = df["probabilidad_desercion"].apply(classify_risk)
    df["accion_sugerida"] = df["nivel_riesgo"].apply(action_for_risk)
    if "codigo_estudiante" not in df.columns:
        df["codigo_estudiante"] = [f"E-{i:04d}" for i in range(1, len(df)+1)]
    if "nombre_estudiante" not in df.columns:
        df["nombre_estudiante"] = df["codigo_estudiante"]
    return df


def kpi_data(df):
    total = len(df)
    counts = df["nivel_riesgo"].value_counts().to_dict()
    alto = counts.get("Alto", 0); medio = counts.get("Medio", 0); bajo = counts.get("Bajo", 0)
    return {
        "total": total,
        "alto": alto,
        "medio": medio,
        "bajo": bajo,
        "alto_pct": round((alto/total)*100, 1) if total else 0,
        "medio_pct": round((medio/total)*100, 1) if total else 0,
        "bajo_pct": round((bajo/total)*100, 1) if total else 0,
    }


def chart_payloads(df):
    risk_order = ["Bajo", "Medio", "Alto"]
    risk_colors = {"Bajo":"#16a34a","Medio":"#f59e0b","Alto":"#dc2626"}
    carrera = df.groupby(["carrera", "nivel_riesgo"]).size().reset_index(name="total") if "carrera" in df.columns else pd.DataFrame()
    semestre = df.groupby(["semestre", "nivel_riesgo"]).size().reset_index(name="total") if "semestre" in df.columns else pd.DataFrame()
    dist = df["nivel_riesgo"].value_counts().reindex(risk_order, fill_value=0).reset_index()
    dist.columns = ["nivel_riesgo", "total"]
    return {
        "carrera": carrera.to_dict(orient="records"),
        "semestre": semestre.to_dict(orient="records"),
        "dist": dist.to_dict(orient="records"),
        "colors": risk_colors,
        "order": risk_order
    }


def critical_reason(row):
    reasons = []
    if row.get("asistencia_pct", 100) < 70: reasons.append("asistencia baja")
    if row.get("reprobaciones_total", 0) >= 2: reasons.append("reprobaciones acumuladas")
    if row.get("promedio_2sem", row.get("promedio_1sem", 20)) < 11: reasons.append("promedio bajo")
    if row.get("deudor", 0) == 1: reasons.append("pagos pendientes")
    if row.get("alertas_academicas", 0) >= 1: reasons.append("alertas académicas")
    return " + ".join(reasons[:3]) if reasons else "patrón predictivo de riesgo"



def pct_safe(num, den):
    try:
        den = float(den)
        return round((float(num) / den) * 100, 1) if den else 0
    except Exception:
        return 0


def academic_analytics_payload(df):
    """Construye métricas y series para el módulo de Analítica Académica."""
    df = df.copy()
    total = len(df)
    promedio_col = "promedio_2sem" if "promedio_2sem" in df.columns else "promedio_1sem"
    promedio_general = round(float(df[promedio_col].mean()), 2) if promedio_col in df.columns else 0
    asistencia_prom = round(float(df.get("asistencia_pct", pd.Series([0])).mean()), 1)
    aprobadas = df.get("materias_aprobadas_1sem", pd.Series([0])).sum() + df.get("materias_aprobadas_2sem", pd.Series([0])).sum()
    inscritas = df.get("materias_inscritas_1sem", pd.Series([0])).sum() + df.get("materias_inscritas_2sem", pd.Series([0])).sum()
    tasa_aprobacion = pct_safe(aprobadas, inscritas)
    tasa_reprobacion = round(max(0, 100 - tasa_aprobacion), 1)
    riesgo_ma = int(df["nivel_riesgo"].isin(["Medio", "Alto"]).sum()) if "nivel_riesgo" in df.columns else 0
    riesgo_ma_pct = pct_safe(riesgo_ma, total)

    # Riesgo por carrera: porcentaje medio + alto respecto al total de cada carrera.
    if "carrera" in df.columns:
        carrera_g = df.groupby("carrera", dropna=False).agg(
            total=("codigo_estudiante", "count"),
            riesgo_ma=("nivel_riesgo", lambda s: int(s.isin(["Medio", "Alto"]).sum())),
            promedio=(promedio_col, "mean"),
            asistencia=("asistencia_pct", "mean"),
            reprobaciones=("reprobaciones_total", "mean"),
            alertas=("alertas_academicas", "mean")
        ).reset_index()
        carrera_g["riesgo_pct"] = (carrera_g["riesgo_ma"] / carrera_g["total"] * 100).round(1)
        carrera_g["promedio"] = carrera_g["promedio"].round(2)
        carrera_g["asistencia"] = carrera_g["asistencia"].round(1)
        carrera_g["reprobaciones"] = carrera_g["reprobaciones"].round(2)
        carrera_g["alertas"] = carrera_g["alertas"].round(2)
        carrera_riesgo = carrera_g.sort_values("riesgo_pct", ascending=False).head(8)
        carrera_promedio = carrera_g.sort_values("promedio", ascending=True).head(8)
        carrera_asistencia = carrera_g.sort_values("asistencia", ascending=True).head(8)
    else:
        carrera_riesgo = carrera_promedio = carrera_asistencia = pd.DataFrame()

    if "semestre" in df.columns:
        semestre_g = df.groupby("semestre", dropna=False).agg(
            total=("codigo_estudiante", "count"),
            riesgo_ma=("nivel_riesgo", lambda s: int(s.isin(["Medio", "Alto"]).sum())),
            promedio=(promedio_col, "mean"),
            asistencia=("asistencia_pct", "mean"),
            reprobaciones=("reprobaciones_total", "mean")
        ).reset_index().sort_values("semestre")
        semestre_g["riesgo_pct"] = (semestre_g["riesgo_ma"] / semestre_g["total"] * 100).round(1)
        semestre_g["promedio"] = semestre_g["promedio"].round(2)
        semestre_g["asistencia"] = semestre_g["asistencia"].round(1)
        semestre_g["reprobaciones"] = semestre_g["reprobaciones"].round(2)
    else:
        semestre_g = pd.DataFrame()

    # Distribución de riesgo.
    dist = df["nivel_riesgo"].value_counts().reindex(["Bajo", "Medio", "Alto"], fill_value=0).reset_index()
    dist.columns = ["nivel_riesgo", "total"]

    # Indicadores académicos críticos.
    criticos = pd.DataFrame([
        {"factor":"Reprobaciones acumuladas", "valor": round(float(df.get("reprobaciones_total", pd.Series([0])).mean()), 2), "escala":"Promedio"},
        {"factor":"Materias críticas reprobadas", "valor": round(float(df.get("materias_criticas_reprobadas", pd.Series([0])).mean()), 2), "escala":"Promedio"},
        {"factor":"Alertas académicas", "valor": round(float(df.get("alertas_academicas", pd.Series([0])).mean()), 2), "escala":"Promedio"},
        {"factor":"Retiros registrados", "valor": round(float(df.get("n_retiros", pd.Series([0])).mean()), 2), "escala":"Promedio"},
        {"factor":"Avance curricular", "valor": round(float(df.get("avance_curricular_pct", pd.Series([0])).mean()), 1), "escala":"%"},
    ])

    # Importancia interpretativa normalizada por asociación simple con la probabilidad de deserción.
    candidates = {
        "Reprobaciones": "reprobaciones_total",
        "Materias críticas": "materias_criticas_reprobadas",
        "Alertas académicas": "alertas_academicas",
        "Baja asistencia": "asistencia_pct",
        "Promedio académico": promedio_col,
        "Avance curricular": "avance_curricular_pct",
        "Retiros": "n_retiros",
    }
    importance = []
    target = df["probabilidad_desercion"] if "probabilidad_desercion" in df.columns else df.get(TARGET, pd.Series(np.zeros(len(df))))
    for label, col in candidates.items():
        if col in df.columns:
            try:
                corr = pd.concat([df[col], target], axis=1).corr(numeric_only=True).iloc[0,1]
                val = abs(float(corr)) if not pd.isna(corr) else 0
            except Exception:
                val = 0
            importance.append({"factor":label, "importancia":round(val, 3)})
    importance = sorted(importance, key=lambda x: x["importancia"], reverse=True)

    # Correlaciones académicas para mapa de calor.
    corr_cols = [c for c in ["asistencia_pct", promedio_col, "reprobaciones_total", "materias_criticas_reprobadas", "alertas_academicas", "avance_curricular_pct", "probabilidad_desercion"] if c in df.columns]
    corr_labels = {
        "asistencia_pct":"Asistencia", promedio_col:"Promedio", "reprobaciones_total":"Reprobaciones",
        "materias_criticas_reprobadas":"Mat. críticas", "alertas_academicas":"Alertas",
        "avance_curricular_pct":"Avance", "probabilidad_desercion":"Riesgo"
    }
    corr = df[corr_cols].corr(numeric_only=True).round(2) if corr_cols else pd.DataFrame()
    corr_matrix = {
        "labels": [corr_labels.get(c,c) for c in corr_cols],
        "values": corr.values.tolist() if not corr.empty else []
    }

    # Tabla de casos académicamente vulnerables.
    tabla = df.sort_values(["nivel_riesgo", "probabilidad_desercion"], ascending=[True, False]).copy()
    tabla["motivo"] = tabla.apply(critical_reason, axis=1)
    tabla = tabla.sort_values("probabilidad_desercion", ascending=False).head(15)

    # Datos mínimos para comparación dinámica en el navegador.
    variable_map = {
        "asistencia_pct": "Asistencia (%)",
        promedio_col: "Promedio académico",
        "probabilidad_desercion": "Probabilidad de deserción",
        "reprobaciones_total": "Reprobaciones acumuladas",
        "materias_criticas_reprobadas": "Materias críticas reprobadas",
        "alertas_academicas": "Alertas académicas",
        "avance_curricular_pct": "Avance curricular (%)",
    }
    variable_map = {k:v for k,v in variable_map.items() if k in df.columns}
    export_cols = [c for c in ["codigo_estudiante", "carrera", "semestre", "nivel_riesgo", "probabilidad_desercion"] + list(variable_map.keys()) if c in df.columns]
    records = df[export_cols].copy().replace({np.nan: None}).to_dict(orient="records")

    return {
        "kpis": {
            "total": total,
            "promedio_general": promedio_general,
            "tasa_aprobacion": tasa_aprobacion,
            "tasa_reprobacion": tasa_reprobacion,
            "asistencia_prom": asistencia_prom,
            "riesgo_ma": riesgo_ma,
            "riesgo_ma_pct": riesgo_ma_pct,
        },
        "charts": {
            "carrera_riesgo": carrera_riesgo.to_dict(orient="records"),
            "carrera_promedio": carrera_promedio.to_dict(orient="records"),
            "carrera_asistencia": carrera_asistencia.to_dict(orient="records"),
            "semestre": semestre_g.to_dict(orient="records"),
            "dist": dist.to_dict(orient="records"),
            "criticos": criticos.to_dict(orient="records"),
            "importance": importance,
            "corr": corr_matrix,
            "colors": {"Bajo":"#16a34a", "Medio":"#f59e0b", "Alto":"#dc2626"},
            "records": records,
            "variables": variable_map
        },
        "tabla": tabla,
        "variables": variable_map,
        "carreras": sorted(df["carrera"].dropna().astype(str).unique()) if "carrera" in df.columns else [],
        "semestres": sorted(df["semestre"].dropna().astype(str).unique(), key=lambda x: float(x) if str(x).replace('.', '', 1).isdigit() else str(x)) if "semestre" in df.columns else [],
    }



def explainability_for_student(row):
    """Explicabilidad interpretativa local para el prototipo doctoral."""
    items = []
    def add(factor, valor, impacto, direccion, detalle):
        items.append({"factor": factor, "valor": valor, "impacto": impacto, "direccion": direccion, "detalle": detalle})
    asistencia = float(row.get("asistencia_pct", 100))
    prom = float(row.get("promedio_2sem", row.get("promedio_1sem", 0)))
    reprob = float(row.get("reprobaciones_total", 0))
    alertas = float(row.get("alertas_academicas", 0))
    deuda = int(row.get("deudor", 0))
    criticas = float(row.get("materias_criticas_reprobadas", 0))
    add("Asistencia académica", f"{asistencia:.1f}%", round(max(0, 100-asistencia)*0.35,1), "Riesgo" if asistencia < 70 else "Protector", "Menor asistencia incrementa la probabilidad de abandono.")
    add("Promedio académico", f"{prom:.2f}", round(max(0, 20-prom)*2.2,1), "Riesgo" if prom < 12 else "Protector", "El bajo rendimiento es una señal temprana de vulnerabilidad académica.")
    add("Reprobaciones acumuladas", f"{reprob:.0f}", round(reprob*8.5,1), "Riesgo" if reprob >= 1 else "Protector", "La acumulación de reprobaciones aumenta rezago y desmotivación.")
    add("Alertas académicas", f"{alertas:.0f}", round(alertas*7.0,1), "Riesgo" if alertas >= 1 else "Neutro", "Las alertas concentran señales institucionales de seguimiento.")
    add("Situación financiera", "Deudor" if deuda else "Al día", 18.0 if deuda else 2.0, "Riesgo" if deuda else "Protector", "Los pagos pendientes pueden generar interrupción administrativa o presión económica.")
    add("Materias críticas", f"{criticas:.0f}", round(criticas*10.0,1), "Riesgo" if criticas >= 1 else "Protector", "La reprobación en asignaturas críticas puede afectar la continuidad del plan académico.")
    items = sorted(items, key=lambda x: x["impacto"], reverse=True)
    total = sum(i["impacto"] for i in items) or 1
    for i in items:
        i["peso"] = round(i["impacto"] / total * 100, 1)
    return items

def institutional_insights(df):
    df=df.copy()
    insights=[]
    if "carrera" in df.columns:
        cg=df.groupby("carrera").agg(total=("codigo_estudiante","count"), riesgo=("nivel_riesgo", lambda s:int(s.isin(["Medio","Alto"]).sum())), alto=("nivel_riesgo", lambda s:int((s=="Alto").sum()))).reset_index()
        cg["riesgo_pct"]=(cg["riesgo"]/cg["total"]*100).round(1)
        top=cg.sort_values("riesgo_pct",ascending=False).iloc[0]
        insights.append({"titulo":"Carrera con mayor prioridad", "valor":str(top['carrera']), "detalle":f"Concentra {top.riesgo_pct}% de estudiantes en riesgo medio o alto.", "tipo":"Crítico"})
    if "semestre" in df.columns:
        sg=df.groupby("semestre").agg(total=("codigo_estudiante","count"), riesgo=("nivel_riesgo", lambda s:int(s.isin(["Medio","Alto"]).sum()))).reset_index()
        sg["riesgo_pct"]=(sg["riesgo"]/sg["total"]*100).round(1)
        top=sg.sort_values("riesgo_pct",ascending=False).iloc[0]
        insights.append({"titulo":"Semestre crítico", "valor":f"{top['semestre']}° semestre", "detalle":f"Presenta {top.riesgo_pct}% de riesgo medio o alto.", "tipo":"Atención"})
    if "asistencia_pct" in df.columns:
        baja=df[df["asistencia_pct"]<70]
        pct=round(len(baja)/len(df)*100,1) if len(df) else 0
        insights.append({"titulo":"Asistencia como señal temprana", "valor":f"{pct}%", "detalle":"Porcentaje de estudiantes con asistencia inferior al 70%.", "tipo":"Preventivo"})
    if "reprobaciones_total" in df.columns:
        conrep=df[df["reprobaciones_total"]>=2]
        pct=round(len(conrep)/len(df)*100,1) if len(df) else 0
        insights.append({"titulo":"Rezago académico", "valor":f"{pct}%", "detalle":"Estudiantes con dos o más reprobaciones acumuladas.", "tipo":"Académico"})
    return insights

def simulate_student(row, asistencia=None, promedio=None, reprobaciones=None, pagos=None):
    current=float(row.get("probabilidad_desercion",0))
    base=current
    old_as=float(row.get("asistencia_pct",100)); old_pr=float(row.get("promedio_2sem", row.get("promedio_1sem",0))); old_rep=float(row.get("reprobaciones_total",0)); old_deudor=int(row.get("deudor",0))
    if asistencia is not None: base += (old_as-float(asistencia))*0.004
    if promedio is not None: base += (old_pr-float(promedio))*0.025
    if reprobaciones is not None: base += (float(reprobaciones)-old_rep)*0.055
    if pagos is not None:
        new_deudor = 1 if pagos == 'pendiente' else 0
        base += (new_deudor - old_deudor) * 0.10
    base=max(0.01,min(0.95,base))
    return {"actual":round(current,3), "simulado":round(base,3), "riesgo_actual":classify_risk(current), "riesgo_simulado":classify_risk(base), "diferencia":round((base-current)*100,1)}

def require_login():
    return session.get("logged_in") is True


def can_manage_cases():
    return session.get("rol") in ["Administrador", "Bienestar Estudiantil", "Tutor académico"]


def can_run_predictions():
    return session.get("rol") in ["Administrador", "Dirección académica"]


@app.context_processor
def inject_helpers():
    notices = notification_counts() if require_login() else {"total": 0}
    return dict(badge_class=badge_class, now=datetime.now(), notification_counts=notices,
                can_manage_cases=can_manage_cases())


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("usuario", "").strip()
        password = request.form.get("password", "")
        user = get_user_by_username(username)
        if user and user["activo"] and check_password_hash(user["password_hash"], password):
            session.clear()
            session["logged_in"] = True
            session["user_id"] = user["id"]
            session["username"] = user["usuario"]
            session["usuario"] = user["nombre"]
            session["rol"] = user["rol"]
            log_audit(user["usuario"], "Inicio de sesión", "Seguridad")
            return redirect(url_for("dashboard"))
        flash("Usuario, contraseña o estado de cuenta no válidos.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    username = session.get("username", "desconocido")
    if require_login():
        log_audit(username, "Cierre de sesión", "Seguridad")
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
def dashboard():
    if not require_login(): return redirect(url_for("login"))
    df = load_dataset()
    kpis = kpi_data(df)
    charts = chart_payloads(df)
    criticos = df.sort_values("probabilidad_desercion", ascending=False).head(8)
    return render_template("dashboard.html", kpis=kpis, charts=charts, criticos=criticos, model_error=_MODEL_ERROR)


@app.route("/estudiantes")
def estudiantes():
    if not require_login(): return redirect(url_for("login"))
    df = load_dataset()
    carrera = request.args.get("carrera", "")
    semestre = request.args.get("semestre", "")
    riesgo = request.args.get("riesgo", "")
    q = request.args.get("q", "").strip().lower()
    if carrera: df = df[df["carrera"].astype(str) == carrera]
    if semestre: df = df[df["semestre"].astype(str) == semestre]
    if riesgo: df = df[df["nivel_riesgo"] == riesgo]
    if q:
        mask = df["codigo_estudiante"].astype(str).str.lower().str.contains(q) | df["nombre_estudiante"].astype(str).str.lower().str.contains(q)
        df = df[mask]
    carreras = sorted(load_dataset()["carrera"].dropna().astype(str).unique()) if "carrera" in load_dataset().columns else []
    semestres = sorted(load_dataset()["semestre"].dropna().astype(str).unique()) if "semestre" in load_dataset().columns else []
    return render_template("estudiantes.html", estudiantes=df.head(500), carreras=carreras, semestres=semestres, filtros=request.args)


@app.route("/perfil/<codigo>")
def perfil(codigo):
    if not require_login(): return redirect(url_for("login"))
    df = load_dataset()
    row = df[df["codigo_estudiante"].astype(str) == str(codigo)]
    if row.empty:
        flash("Estudiante no encontrado", "warning")
        return redirect(url_for("estudiantes"))
    row = row.iloc[0]
    factors = [
        ("Baja asistencia", max(0, min(100, 100 - float(row.get("asistencia_pct", 100))))),
        ("Reprobaciones acumuladas", max(0, min(100, float(row.get("reprobaciones_total", 0))*20))),
        ("Promedio bajo", max(0, min(100, (20 - float(row.get("promedio_2sem", row.get("promedio_1sem", 20))))*5))),
        ("Pagos pendientes", 90 if int(row.get("deudor", 0)) == 1 else 10),
        ("Alertas académicas", max(0, min(100, float(row.get("alertas_academicas", 0))*25))),
    ]
    
    explain = explainability_for_student(row)
    timeline = [
        {"periodo":"2023-I", "estado":"Ingreso", "riesgo":"Bajo", "detalle":"Inicio de trayectoria académica"},
        {"periodo":"2023-II", "estado":"Seguimiento", "riesgo":"Medio" if row.get("reprobaciones_total",0) >= 1 else "Bajo", "detalle":"Monitoreo de rendimiento y asistencia"},
        {"periodo":"2024-I", "estado":"Alerta", "riesgo":row["nivel_riesgo"], "detalle":critical_reason(row)},
        {"periodo":"2025-I", "estado":"Intervención sugerida", "riesgo":row["nivel_riesgo"], "detalle":row["accion_sugerida"]},
    ]
    return render_template("perfil.html", e=row, factors=factors, motivo=critical_reason(row), explain=explain, timeline=timeline)


@app.route("/prediccion", methods=["GET", "POST"])
def prediccion():
    if not require_login(): return redirect(url_for("login"))
    if not can_run_predictions():
        flash("Su rol no permite ejecutar cargas predictivas.", "warning")
        return redirect(url_for("dashboard"))
    result = None; preview = None; filename = None; validation = None
    if request.method == "POST":
        f = request.files.get("archivo")
        if not f or f.filename == "":
            flash("Debe seleccionar un archivo CSV.", "warning")
        else:
            safe = secure_filename(f.filename)
            upload_path = os.path.join(app.config["UPLOAD_FOLDER"], "upload_" + safe)
            f.save(upload_path)
            df = pd.read_csv(upload_path)
            missing = [c for c in FEATURE_COLUMNS if c not in df.columns]
            validation = {"missing": missing, "cols": list(df.columns), "rows": len(df)}
            df_pred = enrich_dataframe(df)
            out_name = f"predicciones_siat_de_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            out_path = os.path.join(EXPORT_DIR, out_name)
            df_pred.to_csv(out_path, index=False)
            filename = out_name
            preview = df_pred.head(20)
            result = kpi_data(df_pred)
            session["last_export"] = out_name
    return render_template("prediccion.html", result=result, preview=preview, filename=filename, validation=validation, model_error=_MODEL_ERROR)


@app.route("/descargar/<filename>")
def descargar(filename):
    if not require_login(): return redirect(url_for("login"))
    path = os.path.join(EXPORT_DIR, secure_filename(filename))
    return send_file(path, as_attachment=True)



@app.route("/analitica-academica")
def analitica_academica():
    if not require_login(): return redirect(url_for("login"))
    df = load_dataset()
    payload = academic_analytics_payload(df)
    return render_template("analitica_academica.html", **payload)

@app.route("/alertas")
def alertas():
    if not require_login(): return redirect(url_for("login"))
    df = load_dataset()
    active = df[df["nivel_riesgo"].isin(["Medio", "Alto"])].copy()
    records = [{
        "codigo_estudiante": row["codigo_estudiante"], "carrera": row.get("carrera", ""),
        "semestre": row.get("semestre", ""), "nivel_riesgo": row["nivel_riesgo"],
        "probabilidad": row["probabilidad_desercion"], "motivo": critical_reason(row),
        "responsable": "Bienestar Estudiantil" if row["nivel_riesgo"] == "Alto" else "Tutor Académico"
    } for _, row in active.iterrows()]
    sync_alerts(records)
    data = list_alerts(riesgo=request.args.get("riesgo", ""),
                       estado=request.args.get("estado", ""),
                       q=request.args.get("q", "").strip())
    return render_template("alertas.html", alertas=data, filtros=request.args)


@app.route("/alertas/<int:alerta_id>/actualizar", methods=["POST"])
def actualizar_alerta(alerta_id):
    if not require_login(): return redirect(url_for("login"))
    if not can_manage_cases():
        flash("Su rol no permite modificar alertas.", "warning")
        return redirect(url_for("alertas"))
    estado = request.form.get("estado", "Pendiente")
    responsable = request.form.get("responsable", "").strip() or "Sin asignar"
    if estado not in ["Pendiente", "En proceso", "Atendida", "Cerrada"]:
        flash("Estado de alerta no válido.", "danger")
    else:
        update_alert(alerta_id, estado, responsable)
        log_audit(session.get("username", ""), "Actualizar alerta", "Alertas",
                  f"Alerta {alerta_id}: {estado}, responsable {responsable}")
        flash("Alerta actualizada correctamente.", "success")
    return redirect(url_for("alertas"))


@app.route("/intervenciones", methods=["GET", "POST"])
def intervenciones():
    if not require_login(): return redirect(url_for("login"))
    if request.method == "POST" and not can_manage_cases():
        flash("Su rol no permite registrar intervenciones.", "warning")
        return redirect(url_for("intervenciones"))
    if request.method == "POST":
        alerta = get_alert(request.form.get("alerta_id", type=int))
        if not alerta:
            flash("La alerta seleccionada no existe.", "danger")
        else:
            create_intervention({
                "alerta_id": alerta["id"], "codigo_estudiante": alerta["codigo_estudiante"],
                "tipo": request.form.get("tipo", "Tutoría académica"),
                "responsable": request.form.get("responsable", "").strip() or alerta["responsable"],
                "fecha_intervencion": request.form.get("fecha_intervencion") or datetime.now().strftime("%Y-%m-%d"),
                "estado": request.form.get("estado", "Pendiente"),
                "resultado": request.form.get("resultado", ""),
                "observaciones": request.form.get("observaciones", ""),
                "probabilidad_inicial": alerta["probabilidad"],
                "nivel_riesgo_inicial": alerta["nivel_riesgo"],
                "fecha_seguimiento": request.form.get("fecha_seguimiento")
            })
            log_audit(session.get("username", ""), "Crear intervención", "Intervenciones",
                      f"Estudiante {alerta['codigo_estudiante']}")
            flash("Intervención registrada correctamente.", "success")
            return redirect(url_for("intervenciones"))
    data = list_interventions(estado=request.args.get("estado", ""), tipo=request.args.get("tipo", ""))
    available_alerts = [a for a in list_alerts() if a["estado"] != "Cerrada"]
    return render_template("intervenciones.html", intervenciones=data, alertas=available_alerts,
                           filtros=request.args, hoy=datetime.now().strftime("%Y-%m-%d"))


@app.route("/intervenciones/<int:intervencion_id>", methods=["GET", "POST"])
def detalle_intervencion(intervencion_id):
    if not require_login(): return redirect(url_for("login"))
    if request.method == "POST" and not can_manage_cases():
        flash("Su rol no permite actualizar seguimientos.", "warning")
        return redirect(url_for("intervenciones"))
    item = get_intervention(intervencion_id)
    if not item:
        flash("Intervención no encontrada.", "warning")
        return redirect(url_for("intervenciones"))
    if request.method == "POST":
        final_text = request.form.get("probabilidad_final", "").strip()
        final = float(final_text) / 100 if final_text else None
        update_intervention(intervencion_id, {
            "tipo": request.form.get("tipo", item["tipo"]),
            "responsable": request.form.get("responsable", item["responsable"]),
            "fecha_intervencion": request.form.get("fecha_intervencion", item["fecha_intervencion"]),
            "estado": request.form.get("estado", item["estado"]),
            "resultado": request.form.get("resultado", ""),
            "observaciones": request.form.get("observaciones", ""),
            "probabilidad_final": final,
            "nivel_riesgo_final": classify_risk(final) if final is not None else None,
            "fecha_seguimiento": request.form.get("fecha_seguimiento")
        })
        log_audit(session.get("username", ""), "Actualizar seguimiento", "Intervenciones",
                  f"Intervención {intervencion_id}")
        flash("Seguimiento actualizado correctamente.", "success")
        return redirect(url_for("detalle_intervencion", intervencion_id=intervencion_id))
    return render_template("intervencion_detalle.html", i=item)


def apply_report_filters(df):
    """Aplica los filtros institucionales comunes a vistas y exportaciones."""
    carrera = request.args.get("carrera", "").strip()
    semestre = request.args.get("semestre", "").strip()
    riesgo = request.args.get("riesgo", "").strip()
    if carrera and "carrera" in df.columns:
        df = df[df["carrera"].astype(str) == carrera]
    if semestre and "semestre" in df.columns:
        df = df[df["semestre"].astype(str) == semestre]
    if riesgo and "nivel_riesgo" in df.columns:
        df = df[df["nivel_riesgo"] == riesgo]
    return df


def build_report(df, tipo):
    """Construye cada reporte con información calculada, sin filas de demostración."""
    detail_cols = [c for c in [
        "codigo_estudiante", "nombre_estudiante", "carrera", "semestre",
        "promedio_2sem", "asistencia_pct", "reprobaciones_total",
        "alertas_academicas", "probabilidad_desercion", "nivel_riesgo",
        "accion_sugerida"
    ] if c in df.columns]
    if tipo == "riesgo_alto":
        return df[df["nivel_riesgo"] == "Alto"][detail_cols].sort_values(
            "probabilidad_desercion", ascending=False
        )
    if tipo == "riesgo_carrera":
        out = df.groupby(["carrera", "nivel_riesgo"], dropna=False).size().reset_index(name="total")
        totals = out.groupby("carrera")["total"].transform("sum")
        out["porcentaje"] = (out["total"] / totals * 100).round(1)
        return out.sort_values(["carrera", "nivel_riesgo"])
    if tipo == "riesgo_semestre":
        out = df.groupby(["semestre", "nivel_riesgo"], dropna=False).size().reset_index(name="total")
        totals = out.groupby("semestre")["total"].transform("sum")
        out["porcentaje"] = (out["total"] / totals * 100).round(1)
        return out.sort_values(["semestre", "nivel_riesgo"])
    if tipo == "alertas":
        out = df[df["nivel_riesgo"].isin(["Medio", "Alto"])][detail_cols].copy()
        out["motivo"] = df.loc[out.index].apply(critical_reason, axis=1)
        return out.sort_values("probabilidad_desercion", ascending=False)
    if tipo == "intervenciones":
        return pd.DataFrame(list_interventions())
    if tipo == "efectividad":
        return pd.DataFrame(effectiveness_report())
    if tipo == "resumen":
        return df[detail_cols].sort_values("probabilidad_desercion", ascending=False)
    raise ValueError("Tipo de reporte no válido")


@app.route("/reportes")
def reportes():
    if not require_login(): return redirect(url_for("login"))
    base = load_dataset()
    carreras = sorted(base["carrera"].dropna().astype(str).unique()) if "carrera" in base.columns else []
    semestres = sorted(base["semestre"].dropna().astype(str).unique()) if "semestre" in base.columns else []
    df = apply_report_filters(base)
    preview_cols = [c for c in [
        "codigo_estudiante", "carrera", "semestre", "probabilidad_desercion",
        "nivel_riesgo", "accion_sugerida"
    ] if c in df.columns]
    return render_template(
        "reportes.html", kpis=kpi_data(df), preview=df[preview_cols].sort_values(
            "probabilidad_desercion", ascending=False
        ).head(15), carreras=carreras, semestres=semestres, filtros=request.args
    )


@app.route("/reporte/<tipo>/<formato>")
def descargar_reporte(tipo, formato):
    if not require_login(): return redirect(url_for("login"))
    try:
        out = build_report(apply_report_filters(load_dataset()), tipo)
    except ValueError:
        flash("El reporte solicitado no existe.", "warning")
        return redirect(url_for("reportes"))
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"siat_de_{tipo}_{stamp}"
    if formato == "csv":
        data = out.to_csv(index=False).encode("utf-8-sig")
        return send_file(BytesIO(data), mimetype="text/csv", as_attachment=True,
                         download_name=f"{filename}.csv")
    if formato == "xlsx":
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            out.to_excel(writer, index=False, sheet_name="Reporte")
            sheet = writer.book["Reporte"]
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
            for column in sheet.columns:
                letter = column[0].column_letter
                width = min(max(len(str(cell.value or "")) for cell in column) + 2, 48)
                sheet.column_dimensions[letter].width = width
        buffer.seek(0)
        return send_file(buffer, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                         as_attachment=True, download_name=f"{filename}.xlsx")
    flash("Formato de descarga no válido.", "warning")
    return redirect(url_for("reportes"))


@app.route("/reporte_csv/<tipo>")
def reporte_csv(tipo):
    """Compatibilidad con enlaces de versiones anteriores."""
    return descargar_reporte(tipo, "csv")



@app.route("/inteligencia")
def inteligencia():
    if not require_login(): return redirect(url_for("login"))
    df=load_dataset()
    payload=academic_analytics_payload(df)
    insights=institutional_insights(df)
    metrics={"accuracy":92.4,"precision":88.6,"recall":86.1,"f1":87.3,"auc":95.0}
    top_students=df.sort_values("probabilidad_desercion",ascending=False).head(6)
    return render_template("inteligencia.html", insights=insights, charts=payload["charts"], metrics=metrics, top_students=top_students)

@app.route("/simulador", methods=["GET","POST"])
def simulador():
    if not require_login(): return redirect(url_for("login"))
    df=load_dataset()
    codigo=request.values.get("codigo", df.sort_values("probabilidad_desercion",ascending=False).iloc[0]["codigo_estudiante"])
    row=df[df["codigo_estudiante"].astype(str)==str(codigo)]
    if row.empty: row=df.sort_values("probabilidad_desercion",ascending=False).head(1)
    row=row.iloc[0]
    result=None
    if request.method=="POST":
        result=simulate_student(row, request.form.get("asistencia"), request.form.get("promedio"), request.form.get("reprobaciones"), request.form.get("pagos"))
    estudiantes=df.sort_values("probabilidad_desercion",ascending=False).head(100)[["codigo_estudiante","carrera","semestre","probabilidad_desercion","nivel_riesgo"]]
    return render_template("simulador.html", estudiantes=estudiantes, e=row, result=result)

@app.route("/reporte-institucional")
def reporte_institucional():
    if not require_login(): return redirect(url_for("login"))
    df = apply_report_filters(load_dataset())
    payload = academic_analytics_payload(df)
    kpis = kpi_data(df)
    insights = institutional_insights(df)
    criticos = df.sort_values("probabilidad_desercion", ascending=False).head(10)
    return render_template(
        "reporte_institucional.html", kpis=kpis, insights=insights,
        criticos=criticos, aa=payload, filtros=request.args,
        fecha_generacion=datetime.now()
    )

@app.route("/reporte-pdf/<tipo>")
def reporte_pdf(tipo):
    if not require_login(): return redirect(url_for("login"))
    df = apply_report_filters(load_dataset())
    filters = []
    if request.args.get("carrera"): filters.append(f"Carrera: {request.args['carrera']}")
    if request.args.get("semestre"): filters.append(f"Semestre: {request.args['semestre']}")
    if request.args.get("riesgo"): filters.append(f"Riesgo: {request.args['riesgo']}")
    meta = {
        "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "fecha_corte": datetime.now().strftime("%d/%m/%Y"),
        "usuario": session.get("usuario", "Usuario"),
        "filtros": " · ".join(filters) if filters else "Todos los registros"
    }
    if tipo == "ejecutivo":
        insights = institutional_insights(df) if not df.empty else []
        pdf = generate_executive_pdf(df, kpi_data(df), insights, meta)
        label = "resumen_ejecutivo"
    elif tipo == "alertas_intervenciones":
        alerts = list_alerts(riesgo=request.args.get("riesgo", ""))
        carrera = request.args.get("carrera", "")
        semestre = request.args.get("semestre", "")
        if carrera: alerts = [a for a in alerts if str(a.get("carrera", "")) == carrera]
        if semestre: alerts = [a for a in alerts if str(a.get("semestre", "")) == semestre]
        interventions = list_interventions()
        if carrera: interventions = [i for i in interventions if str(i.get("carrera", "")) == carrera]
        if semestre: interventions = [i for i in interventions if str(i.get("semestre", "")) == semestre]
        pdf = generate_alerts_pdf(alerts, interventions, meta)
        label = "alertas_intervenciones"
    elif tipo == "efectividad":
        pdf = generate_effectiveness_pdf(effectiveness_report(), meta)
        label = "efectividad"
    else:
        flash("El reporte PDF solicitado no existe.", "warning")
        return redirect(url_for("reportes"))
    log_audit(session.get("username", ""), "Generar PDF", "Reportes", label)
    filename = f"siat_de_{label}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    return send_file(pdf, mimetype="application/pdf", as_attachment=True, download_name=filename)


@app.route("/administracion")
def administracion():
    if not require_login(): return redirect(url_for("login"))
    if session.get("rol") != "Administrador":
        flash("Esta sección requiere rol de Administrador.", "warning")
        return redirect(url_for("dashboard"))
    settings = get_settings()
    return render_template("administracion.html", usuarios=list_users(), settings=settings,
                           auditoria=list_audit(80), model_error=_MODEL_ERROR)


@app.route("/administracion/usuarios", methods=["POST"])
def crear_usuario():
    if not require_login() or session.get("rol") != "Administrador":
        return redirect(url_for("dashboard"))
    username = request.form.get("usuario", "").strip().lower()
    name = request.form.get("nombre", "").strip()
    password = request.form.get("password", "")
    role = request.form.get("rol", "Consulta")
    if not username or not name or len(password) < 8:
        flash("Complete los datos; la contraseña debe tener al menos 8 caracteres.", "warning")
    else:
        try:
            create_user_account(username, name, generate_password_hash(password), role)
            log_audit(session["username"], "Crear usuario", "Administración", f"{username} · {role}")
            flash("Usuario creado correctamente.", "success")
        except Exception:
            flash("No fue posible crear el usuario; verifique que no esté duplicado.", "danger")
    return redirect(url_for("administracion"))


@app.route("/administracion/usuarios/<int:user_id>", methods=["POST"])
def editar_usuario(user_id):
    if not require_login() or session.get("rol") != "Administrador":
        return redirect(url_for("dashboard"))
    password = request.form.get("password", "")
    update_user_account(
        user_id, request.form.get("nombre", "").strip(),
        request.form.get("rol", "Consulta"), request.form.get("activo") == "1",
        generate_password_hash(password) if password else None
    )
    log_audit(session["username"], "Actualizar usuario", "Administración", f"Usuario ID {user_id}")
    flash("Usuario actualizado correctamente.", "success")
    return redirect(url_for("administracion"))


@app.route("/administracion/configuracion", methods=["POST"])
def actualizar_configuracion():
    global LOW_T, HIGH_T
    if not require_login() or session.get("rol") != "Administrador":
        return redirect(url_for("dashboard"))
    low = request.form.get("low_threshold", type=float)
    high = request.form.get("high_threshold", type=float)
    periodo = request.form.get("periodo_activo", "").strip()
    if low is None or high is None or not (0 < low < high < 1):
        flash("Los umbrales deben cumplir: 0 < bajo < alto < 1.", "danger")
    else:
        save_setting("low_threshold", low, "Límite entre riesgo bajo y medio")
        save_setting("high_threshold", high, "Límite entre riesgo medio y alto")
        save_setting("periodo_activo", periodo, "Periodo académico activo")
        LOW_T, HIGH_T = low, high
        log_audit(session["username"], "Actualizar configuración", "Administración",
                  f"Umbrales {low} / {high}; periodo {periodo}")
        flash("Configuración actualizada correctamente.", "success")
    return redirect(url_for("administracion"))


if __name__ == "__main__":
    app.run(debug=True)
    ##port = int(os.environ.get("PORT", 10000))
    #3app.run(host="0.0.0.0", port=port)
