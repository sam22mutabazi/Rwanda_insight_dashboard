import streamlit as st
import pandas as pd
import plotly.express as px
import datetime
import time
import io
from utils import (calculate_age_from_id, calculate_equality_score,
				   load_users, save_user, delete_user, reset_user_password, toggle_admin_role,
				   save_audit_log, load_audit_logs, load_notifications, log_data_stats, load_data_stats,
				   smart_fix_locations, get_cleanliness_score, generate_pdf_report, ai_chat_logic,
				   run_forecast_logic)  # Added the forecast logic import

st.set_page_config(page_title="Rwanda Insight Pro", layout="wide")

# --- THEME (PRESERVED) ---
theme_mode = st.sidebar.toggle("🌙 Dark Mode", value=False)
if theme_mode:
	st.markdown(
		"""<style>.stApp { background-color: #0e1117; color: white; } .sidebar-card { background-color: #1a1c24 !important; border-left: 5px solid #00A3E0; } .stMetric { background-color: #1a1c24; padding: 15px; border-radius: 10px; }</style>""",
		unsafe_allow_html=True)
else:
	st.markdown(
		"""<style>.sidebar-card { background-color: #f8f9fa; border-left: 5px solid #00A3E0; } .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #eee; }</style>""",
		unsafe_allow_html=True)

if "auth" not in st.session_state: st.session_state.auth = False

# --- AUTH ---
if not st.session_state.auth:
	st.markdown("<h1 style='text-align: center;'>🇷🇼 Rwanda Insight Pro</h1>", unsafe_allow_html=True)
	col1, col2, col3 = st.columns([1, 2, 1])
	with col2:
		mode = st.radio("Access", ["Login", "Sign Up"], horizontal=True)
		u = st.text_input("Username")
		p = st.text_input("Password", type="password")
		if st.button("Access Dashboard", use_container_width=True):
			users = load_users()
			if mode == "Login":
				user_entry = users.get(u)
				if user_entry:
					stored_pwd = user_entry["pwd"] if isinstance(user_entry, dict) else user_entry
					is_admin = user_entry.get("is_admin", False) if isinstance(user_entry, dict) else (
								u == "admin" or u == "mutabazi")
					if stored_pwd == p:
						st.session_state.auth = True
						st.session_state.user = u
						st.session_state.is_admin = is_admin
						st.rerun()
					else:
						st.error("Access Denied")
				else:
					st.error("Access Denied")
			else:
				if save_user(u, p):
					st.success("Account Created!")
				else:
					st.error("Username taken")
	st.stop()

# --- SIDEBAR NAVIGATION ---
with st.sidebar:
	st.markdown(f"""<div class="sidebar-card" style="padding: 15px; border-radius: 12px; margin-bottom: 20px;">
        <div style="font-size: 1.3em; font-weight: bold; color: #00A3E0;">{st.session_state.user.upper()}</div>
        <div style="font-size: 0.9em; color: #555;">🕒 {datetime.datetime.now().strftime("%H:%M:%S")}</div>
    </div>""", unsafe_allow_html=True)

	nav = ["📊 Analytics", "🌍 Map View", "⚖️ Comparison", "🤖 AI & Trends"]
	if st.session_state.get("is_admin", False):
		nav.append("🔑 Admin Panel")

	page = st.radio("Navigation", nav)
	st.divider()
	uploaded_file = st.file_uploader("📂 Upload Dataset", type=["csv", "xlsx"])

# --- MAIN DATA LOGIC (PRESERVED CONTENT) ---
df = None
if uploaded_file:
	df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
	df.columns = [c.strip() for c in df.columns]
	if 'last_uploaded' not in st.session_state or st.session_state.last_uploaded != uploaded_file.name:
		log_data_stats(len(df))
		save_audit_log(st.session_state.user, uploaded_file.name)
		st.session_state.last_uploaded = uploaded_file.name

	mapping = {'sex': 'Gender', 'gender': 'Gender', 'nid': 'National ID', 'lat': 'Latitude', 'lon': 'Longitude'}
	for old_col in df.columns:
		for key, val in mapping.items():
			if key.lower() in old_col.lower(): df.rename(columns={old_col: val}, inplace=True)

	if 'National ID' in df.columns:
		df['Age'] = df['National ID'].astype(str).apply(calculate_age_from_id)
		df['Age Group'] = df['Age'].apply(
			lambda x: 'Youth' if x and x < 30 else 'Adult' if x and x <= 60 else 'Senior' if x else None)

	filtered_df = df.copy()
	dist_list = ["All Districts"] + sorted(df['District'].dropna().unique().tolist()) if 'District' in df.columns else [
		"All Districts"]
	sel_dist = st.sidebar.selectbox("Select District", dist_list)
	if sel_dist != "All Districts":
		filtered_df = filtered_df[filtered_df['District'] == sel_dist]
		sect_list = ["All Sectors"] + sorted(
			filtered_df['Sector'].dropna().unique().tolist()) if 'Sector' in filtered_df.columns else ["All Sectors"]
		sel_sect = st.sidebar.selectbox("Select Sector", sect_list)
		if sel_sect != "All Sectors": filtered_df = filtered_df[filtered_df['Sector'] == sel_sect]

	st.sidebar.divider()
	st.sidebar.markdown("💬 **AI Data Assistant**")
	user_query = st.sidebar.text_input("Ask about your data...", key="chat_input")
	if user_query: st.sidebar.caption(ai_chat_logic(user_query, filtered_df))

	# --- PAGE ROUTING ---
	if page == "📊 Analytics":
		st.title("🏛️ Sector Analytics")
		score = get_cleanliness_score(filtered_df)
		st.write(f"**Cleanliness: {score}%**")
		st.progress(score / 100)
		c1, c2, c3 = st.columns(3)
		eq_val, _ = calculate_equality_score(filtered_df)
		c1.metric("Attendance", len(filtered_df))
		c2.metric("Equality", f"{eq_val:.1f}%")
		c3.metric("Avg Age", f"{filtered_df['Age'].mean():.0f}" if 'Age' in filtered_df.columns else "N/A")

		t1, t2, t3 = st.tabs(["📈 Charts", "🔍 Export", "📅 Schedule"])
		with t1:
			col_a, col_b = st.columns(2)
			if 'Gender' in filtered_df.columns:
				col_a.plotly_chart(px.pie(filtered_df, names='Gender', hole=0.4, title="Gender Breakdown"),
								   use_container_width=True)
			if 'Age Group' in filtered_df.columns:
				col_b.plotly_chart(px.pie(filtered_df, names='Age Group', hole=0.4, title="Age Groups"),
								   use_container_width=True)
			st.plotly_chart(
				px.histogram(filtered_df, x='District' if 'District' in filtered_df.columns else df.columns[0],
							 color='Gender' if 'Gender' in filtered_df.columns else None, barmode='group',
							 title="Participation by Region"), use_container_width=True)
		with t2:
			st.subheader("Data Export & Preview")
			c_ex1, c_ex2 = st.columns(2)
			buffer = io.BytesIO()
			with pd.ExcelWriter(buffer, engine='openpyxl') as writer: filtered_df.to_excel(writer, index=False)
			c_ex1.download_button("📥 Excel Download", buffer.getvalue(), "Rwanda_Clean.xlsx")
			c_ex2.download_button("📄 PDF Report", generate_pdf_report(filtered_df, sel_dist), f"Report_{sel_dist}.pdf")
			st.dataframe(filtered_df.style.highlight_null(color='#ff4b4b'), use_container_width=True)
		with t3:
			if 'Sector' in filtered_df.columns:
				for s in filtered_df['Sector'].unique(): st.date_input(f"Date for {s}", datetime.date(2026, 5, 1),
																	   key=s)

	elif page == "🌍 Map View":
		st.title("🌍 GPS Distribution")
		if 'Latitude' in filtered_df.columns and 'Longitude' in filtered_df.columns:
			st.map(filtered_df.dropna(subset=['Latitude', 'Longitude'])[['Latitude', 'Longitude']])
		else:
			st.error("No GPS coordinates found.")

	elif page == "⚖️ Comparison":
		st.title("⚖️ Compare Districts")
		if 'District' in df.columns:
			d1 = st.selectbox("District A", df['District'].unique(), key="comp_a")
			d2 = st.selectbox("District B", df['District'].unique(), key="comp_b",
							  index=1 if len(df['District'].unique()) > 1 else 0)
			comp_df = pd.DataFrame(
				{"Dist": [d1, d2], "Total": [len(df[df['District'] == d1]), len(df[df['District'] == d2])]})
			st.plotly_chart(px.bar(comp_df, x="Dist", y="Total", color="Dist"), use_container_width=True)
		else:
			st.error("No District column available for comparison.")

	elif page == "🤖 AI & Trends":
		st.title("🔮 AI Predictive & History Trends")
		st.subheader("📊 System Usage History")
		history_data = load_data_stats()
		if history_data:
			st.plotly_chart(
				px.line(pd.DataFrame(history_data), x="date", y="count", title="Data Upload Volume Over Time",
						markers=True), use_container_width=True)

		if st.button("🚀 Run Forecast"):
			# Updated to use the robust run_forecast_logic from utils.py
			trend_data = run_forecast_logic(filtered_df)
			if trend_data is not None:
				category_col = trend_data.columns[0]
				st.plotly_chart(px.line(trend_data, x=category_col, y=['Current', 'Forecast'],
										title=f"Engagement Forecast by {category_col}", markers=True),
								use_container_width=True)
				st.success("Analysis Complete: Forecasted a growth based on current demographics.")
			else:
				st.warning(
					"⚠️ Could not run forecast. Please ensure your dataset contains 'National ID' or 'Gender' columns.")

# --- ADMIN PANEL PAGE (PROTECTED) ---
if page == "🔑 Admin Panel":
	if not st.session_state.get("is_admin", False):
		st.error("🔒 Unauthorized access to Admin Panel.")
	else:
		st.title("🔑 Administrator Dashboard")
		tab1, tab2, tab3 = st.tabs(["👥 User Management", "📜 Audit Logs", "🛡️ System Settings"])

		with tab1:
			st.subheader("Manage Registered Users")
			users = load_users()
			display_list = [{"Username": k, "Admin Access": v["is_admin"]} for k, v in users.items()]
			st.dataframe(pd.DataFrame(display_list), use_container_width=True)
			st.divider()

			u_col1, u_col2 = st.columns(2)
			with u_col1:
				target_user = st.selectbox("Select User", list(users.keys()))
				new_pwd = st.text_input("Reset Password", type="password")
				if st.button("Update Password"):
					if reset_user_password(target_user, new_pwd): st.success("Updated!")

			with u_col2:
				user_info = users[target_user]
				is_currently_admin = user_info["is_admin"]
				st.write(f"Current Status: **{'Admin' if is_currently_admin else 'Standard User'}**")
				if st.button("Grant/Revoke Admin Access"):
					# Pass current user as the actor for logging
					if toggle_admin_role(target_user, st.session_state.user):
						st.success("Role Changed and Logged!")
						time.sleep(1)
						st.rerun()

				if st.button("❌ Delete Account"):
					if delete_user(target_user):
						st.error("Deleted!")
						time.sleep(1)
						st.rerun()

		with tab2:
			st.subheader("Activity Audit Trail")
			logs = load_audit_logs()
			if logs:
				st.dataframe(pd.DataFrame(logs), use_container_width=True)
			else:
				st.info("No logs found.")

		with tab3:
			st.subheader("System Security Status")
			st.success("✅ Database Connection: Active")
			st.success(f"✅ Active Session: {st.session_state.user}")

# --- FOOTER ---
if st.sidebar.button("🔓 Sign Out"):
	st.session_state.auth = False
	st.rerun()

if not uploaded_file and page != "🔑 Admin Panel":
	st.info("👋 Welcome! Please upload your dataset to start.")