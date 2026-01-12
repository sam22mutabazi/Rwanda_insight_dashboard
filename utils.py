import pandas as pd
import datetime
import streamlit as st
import json
import os
from fpdf import FPDF
from difflib import get_close_matches

# --- DEPLOYMENT PATH HANDLING ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- STORAGE ---
USER_FILE = os.path.join(BASE_DIR, "users.json")
LOG_FILE = os.path.join(BASE_DIR, "audit_log.json")
NOTIF_FILE = os.path.join(BASE_DIR, "notifications.json")
STATS_FILE = os.path.join(BASE_DIR, "upload_stats.json")


def load_users():
    if not os.path.exists(USER_FILE):
       default = {
          "admin": {"pwd": "rwanda2026", "is_admin": True},
          "mutabazi": {"pwd": "Sam22@", "is_admin": True}
       }
       with open(USER_FILE, "w") as f: json.dump(default, f)
       return default
    with open(USER_FILE, "r") as f:
       data = json.load(f)
       for u in data:
          if isinstance(data[u], str):
             data[u] = {"pwd": data[u], "is_admin": (u == "admin" or u == "mutabazi")}
       return data


def save_user(username, password):
    users = load_users()
    if username in users: return False
    users[username] = {"pwd": password, "is_admin": False}
    with open(USER_FILE, "w") as f: json.dump(users, f)
    add_notification(f"🆕 New Account Created: {username}")
    return True


def toggle_admin_role(username, actor_name):
    users = load_users()
    if username in users and username != "admin":
       old_status = users[username]["is_admin"]
       new_status = not old_status
       users[username]["is_admin"] = new_status
       with open(USER_FILE, "w") as f: json.dump(users, f)
       log_admin_action(actor_name, "Role Change", f"Changed {username} to {'Admin' if new_status else 'User'}")
       return True
    return False


def log_admin_action(actor, action, details):
    logs = load_audit_logs()
    logs.append({
       "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
       "user": actor,
       "action": action,
       "details": details
    })
    with open(LOG_FILE, "w") as f: json.dump(logs, f)


def delete_user(username):
    users = load_users()
    if username == "admin": return False
    if username in users:
       del users[username]
       with open(USER_FILE, "w") as f: json.dump(users, f)
       return True
    return False


def reset_user_password(username, new_password):
    users = load_users()
    if username in users:
       users[username]["pwd"] = new_password
       with open(USER_FILE, "w") as f: json.dump(users, f)
       add_notification(f"🔑 Password Reset: {username}")
       return True
    return False


def add_notification(message):
    notifs = load_notifications()
    notifs.append({"time": datetime.datetime.now().strftime("%H:%M"), "msg": message})
    with open(NOTIF_FILE, "w") as f: json.dump(notifs, f)


def load_notifications():
    if not os.path.exists(NOTIF_FILE): return []
    with open(NOTIF_FILE, "r") as f: return json.load(f)


def save_audit_log(username, filename):
    log_admin_action(username, "Upload", filename)


def load_audit_logs():
    if not os.path.exists(LOG_FILE): return []
    with open(LOG_FILE, "r") as f: return json.load(f)


def log_data_stats(row_count):
    stats = []
    if os.path.exists(STATS_FILE):
       with open(STATS_FILE, "r") as f: stats = json.load(f)
    stats.append({"date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "count": row_count})
    with open(STATS_FILE, "w") as f: json.dump(stats[-20:], f)


def load_data_stats():
    if not os.path.exists(STATS_FILE): return []
    with open(STATS_FILE, "r") as f: return json.load(f)


@st.cache_data
def calculate_age_from_id(nid: str) -> int | None:
    nid = str(nid).split('.')[0].strip()
    if len(nid) != 16 or not nid.isdigit(): return None
    try:
       century = 1900 if nid[0] == '1' else 2000
       year = century + int(nid[6:8])
       return 2026 - year
    except:
       return None


def calculate_equality_score(df):
    if 'Gender' not in df.columns or df.empty: return 0, "No Data"
    counts = df['Gender'].value_counts(normalize=True) * 100
    m, f = counts.get('Male', 0), counts.get('Female', 0)
    balance = 100 - abs(m - f)
    return balance, "💎 Excellent" if balance >= 90 else "✅ Good" if balance >= 70 else "⚠️ Imbalance"


def smart_fix_locations(df):
    cols_to_fix = [c for c in ['District', 'Sector', 'Cell'] if c in df.columns]
    if not cols_to_fix or 'Village' not in df.columns: return df
    ref_data = df.dropna(subset=cols_to_fix).drop_duplicates('Village')
    ref_map = ref_data.set_index('Village')[cols_to_fix].to_dict('index')

    def apply_fix(row):
       if row['Village'] in ref_map:
          for col in cols_to_fix:
             if pd.isna(row[col]): row[col] = ref_map[row['Village']][col]
       return row

    return df.apply(apply_fix, axis=1)


def get_cleanliness_score(df):
    if df.empty: return 0
    total_cells = df.size
    missing_cells = df.isnull().sum().sum()
    score = ((total_cells - missing_cells) / total_cells) * 100
    return int(score)


def run_forecast_logic(df):
    if df is None or df.empty:
       return None
    if 'Age Group' in df.columns:
       trend = df.groupby('Age Group').size().reset_index(name='Current')
       trend['Forecast'] = (trend['Current'] * 1.25).astype(int)
       return trend
    if 'Gender' in df.columns:
       trend = df.groupby('Gender').size().reset_index(name='Current')
       trend['Forecast'] = (trend['Current'] * 1.15).astype(int)
       return trend
    return None


def generate_pdf_report(df, loc_name):
    """
    Fixed: This version accepts both the dataframe (df) and the location name.
    """
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt=f"Rwanda Insight Pro - {loc_name}", ln=True, align='C')
    pdf.set_font("Arial", size=12)
    pdf.ln(10)
    pdf.cell(200, 10, txt=f"Total Participants: {len(df)}", ln=True)
    if 'Age' in df.columns:
       pdf.cell(200, 10, txt=f"Average Age: {df['Age'].mean():.1f}", ln=True)
    pdf.cell(200, 10, txt=f"Report Generated: {datetime.datetime.now().strftime('%Y-%m-%d')}", ln=True)
    return pdf.output(dest='S').encode('latin-1')


def ai_chat_logic(query, df):
    if df is None or df.empty: return "Please upload data first."
    query = query.lower()
    if "how many" in query or "total" in query:
       return f"📊 Found {len(df)} participants for this selection."
    if "gender" in query or "sex" in query:
       if 'Gender' in df.columns:
          m = len(df[df['Gender'].str.lower() == 'male'])
          f = len(df[df['Gender'].str.lower() == 'female'])
          return f"🚻 Gender: {m} Males, {f} Females."
    if "age" in query:
       avg_age = df['Age'].mean() if 'Age' in df.columns else 0
       return f"🎂 Average age is {avg_age:.1f} years."
    return "🤖 Try: 'Total participants', 'Gender breakdown', or 'Average age'."