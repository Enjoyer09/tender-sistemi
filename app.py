import streamlit as st
import pandas as pd
import time
from datetime import datetime
from supabase import create_client, Client

# --- SƏHİFƏ TƏNZİMLƏMƏLƏRİ ---
st.set_page_config(page_title="Global Tender Sistemi", layout="wide")

# --- SUPABASE QOŞULMA ---
try:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    supabase: Client = create_client(url, key)
except:
    st.error("Supabase açarları tapılmadı! Secrets bölməsini yoxlayın.")
    st.stop()

# --- MƏLUMAT BAZASI FUNKSİYALARI ---

def get_data(table_name):
    response = supabase.table(table_name).select("*").execute()
    df = pd.DataFrame(response.data)
    return df

def add_row(table_name, data_dict):
    supabase.table(table_name).insert(data_dict).execute()

def update_order_stage(order_id, new_status, winner, price):
    supabase.table("orders").update({
        "status": new_status,
        "winner": winner,
        "final_price": price
    }).eq("id", order_id).execute()

def delete_orders(order_ids):
    if not order_ids: return
    supabase.table("bids").delete().in_("order_id", order_ids).execute()
    supabase.table("orders").delete().in_("id", order_ids).execute()

def update_user_password(username, new_password):
    response = supabase.table("users").select("*").eq("username", username).execute()
    if response.data:
        supabase.table("users").update({"password": new_password}).eq("username", username).execute()
    else:
        add_row("users", {"username": username, "password": new_password})

# --- Köməkçi Funksiyalar ---
def find_column_by_keyword(columns, keywords):
    for col in columns:
        for key in keywords:
            if key.lower() in str(col).lower():
                return col
    return None

def detect_header_row(df_preview):
    keywords = ['description', 'item', 'mal', 'ad', 'product', 'qty', 'quantity', 'say', 'amount', 'birim', 'sira']
    for idx, row in df_preview.iterrows():
        row_text = " ".join(row.astype(str)).lower()
        match_count = sum(1 for k in keywords if k in row_text)
        if match_count >= 2:
            return idx
    return 0

# --- SESSİYA ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'current_user' not in st.session_state:
    st.session_state['current_user'] = None

# ==========================================
# YAN MENYU
# ==========================================
with st.sidebar:
    st.title("🔐 Giriş Paneli")

    with st.expander("🆘 Admin (Şifrə Sıfırla)"):
        with st.form("admin_reset_form"):
            master_key_input = st.text_input("Master Key", type="password")
            submitted_master = st.form_submit_button("Yoxla")
            if submitted_master:
                if master_key_input.strip() == "admin123":
                    st.session_state['admin_unlocked'] = True
                    st.success("Admin Girişi ✅")
                else:
                    st.error("Səhv Master Key")

        if st.session_state.get('admin_unlocked', False):
            reset_user = st.selectbox("İşçi seçin", ["Admin", "Anar", "Samir", "Vüsal", "Orxan", "Elnur"])
            new_pass_admin = st.text_input("Yeni şifrə", key="rst_pass")
            if st.button("Şifrəni Dəyiş"):
                update_user_password(reset_user, new_pass_admin)
                st.success("Yeniləndi!")

    st.divider()

    if not st.session_state['logged_in']:
        users_list = ["Seçin...", "Admin", "Anar", "Samir", "Vüsal", "Orxan", "Elnur"]
        selected_user = st.selectbox("İşçi Adı", users_list)

        if selected_user != "Seçin...":
            response = supabase.table("users").select("*").eq("username", selected_user).execute()
            user_data = response.data

            if not user_data:
                st.warning("İlk girişinizdir.")
                with st.form("register_form"):
                    new_pass = st.text_input("Yeni Şifrə Təyin Et", type="password")
                    submit_reg = st.form_submit_button("Qeydiyyatdan Keç")
                    if submit_reg:
                        add_row("users", {"username": selected_user, "password": new_pass})
                        st.success("Hazırdır! İndi giriş edin.")
                        time.sleep(1)
                        st.rerun()
            else:
                with st.form("login_form"):
                    password = st.text_input("Şifrənizi yazın", type="password")
                    submit_login = st.form_submit_button("Daxil Ol 🚀")
                    if submit_login:
                        real_pass = user_data[0]['password']
                        if str(real_pass).strip() == str(password).strip():
                            st.session_state['logged_in'] = True
                            st.session_state['current_user'] = selected_user
                            st.rerun()
                        else:
                            st.error("Şifrə yanlışdır!")
    else:
        st.success(f"Xoş gəldin, **{st.session_state['current_user']}**")
        if st.button("Çıxış Et 🔒", type="primary"):
            st.session_state['logged_in'] = False
            st.session_state['current_user'] = None
            st.rerun()

# ==========================================
# ƏSAS EKRAN
# ==========================================

if st.session_state['logged_in']:
    user = st.session_state['current_user']

    # --- DATANI ƏVVƏLDƏN ÇƏKİRİK (Lazım olacaq) ---
    response = supabase.table("orders").select("*").neq("status", "Tamamlandı").execute()
    orders_df = pd.DataFrame(response.data)
    if not orders_df.empty:
        orders_df = orders_df.sort_values(by="id", ascending=False)
    
    if user == "Admin":
        st.info("🔧 Admin Paneli")
        
        # 1. EXCEL YÜKLƏMƏ
        with st.expander("📂 Excel-dən Yüklə", expanded=False):
            uploaded_file = st.file_uploader("Fayl Seç", type=["xlsx", "xls", "csv"])
            header_idx = 0 
            
            if uploaded_file:
                try:
                    file_engine = 'openpyxl'
                    if uploaded_file.name.endswith('.xls'):
                        file_engine = 'xlrd'
                    
                    if uploaded_file.name.endswith('.csv'):
                        df_preview = pd.read_csv(uploaded_file, header=None, nrows=20)
                    else:
                        df_preview = pd.read_excel(uploaded_file, header=None, nrows=20, engine=file_engine)
                    
                    detected_idx = detect_header_row(df_preview)
                    st.write(f"🤖 Təxmin edilən başlıq: {detected_idx}")
                    header_idx = st.number_input("Başlıq Sətri Nömrəsi:", min_value=0, value=int(detected_idx), step=1)

                    if uploaded_file.name.endswith('.csv'):
                        uploaded_file.seek(0)
                        df_final = pd.read_csv(uploaded_file, header=header_idx)
                    else:
                        df_final = pd.read_excel(uploaded_file, header=header_idx, engine=file_engine)

                    st.dataframe(df_final.head(3), height=100)
                    cols = df_final.columns.tolist()
                    
                    c1, c2, c3 = st.columns(3)
                    name_col = c1.selectbox("Malın Adı:", cols, index=0)
                    qty_col = c2.selectbox("Say:", cols, index=1 if len(cols)>1 else 0)
                    unit_col = c3.selectbox("Ölçü:", ["-Yoxdur-"] + cols, index=0)
                    
                    st.caption(f"👀 Seçilən sütundan nümunə: {df_final[name_col].head(3).tolist()}")

                    if st.button("Sistemə Yüklə 📥"):
                        new_orders_list = []
                        count = 0
                        for index, row in df_final.iterrows():
                            prod_val = str(row[name_col])
                            invalid_words = ['nan', 'none', 'subtotal', 'total', 'grand total']
                            if prod_val and prod_val.lower() not in invalid_words and prod_val.strip() != '':
                                try:
                                    q_val = row[qty_col]
                                    if pd.isna(q_val): q_val = 1
                                    q_val = float(q_val)
                                except:
                                    q_val = 1.0
                                
                                u_val = ""
                                if unit_col != "-Yoxdur-":
                                    u_val = str(row[unit_col])
                                    if u_val.lower() == 'nan': u_val = ""

                                new_orders_list.append({
                                    "product_name": prod_val,
                                    "qty": q_val,
                                    "unit": u_val,
                                    "status": "Axtarışda",
                                })
                                count += 1
                        
                        if new_orders_list:
                            supabase.table("orders").insert(new_orders_list).execute()
                            st.success(f"✅ {count} ədəd mal yükləndi.")
                            time.sleep(1)
                            st.rerun()

                except Exception as e:
                    st.error(f"Xəta: {e}")

        # 2. TƏK SİFARİŞ
        with st.expander("➕ Tək Sifariş Yarat"):
            with st.form("add_single"):
                c1, c2, c3 = st.columns([3, 1, 1])
                p_name = c1.text_input("Malın Adı")
                p_qty = c2.number_input("Say", 1, 100)
                p_unit = c3.text_input("Ölçü", value="eded")
                if st.form_submit_button("Əlavə Et"):
                    add_row("orders", {
                        "product_name": p_name,
                        "qty": p_qty,
                        "unit": p_unit,
                        "status": "Axtarışda"
                    })
                    st.toast("Əlavə olundu!")
                    st.rerun()
        st.divider()

    c1, c2 = st.columns([8, 2])
    c1.title(f"👤 {user} - Şəxsi Kabinet")
    if c2.button("🔄 Yenilə"):
        st.rerun()

    tab1, tab2 = st.tabs(["🔥 Aktiv Bazar", "📜 Tarixçə"])

    with tab1:
        if orders_df.empty:
            st.info("Aktiv sifariş yoxdur.")
        else:
            bids_resp = supabase.table("bids").select("*").execute()
            all_bids_df = pd.DataFrame(bids_resp.data)

            # ------------------------------------------------------------------
            # HAMISINI SEÇ MƏNTİQİ (CALLBACK)
            # ------------------------------------------------------------------
            if user == "Admin":
                def toggle_select_all():
                    # Hamısını seç düyməsinin dəyərini oxuyur
                    select_all_state = st.session_state.get('master_select', False)
                    # Bütün ID-ləri həmin dəyərə bərabər edir
                    for oid in orders_df['id']:
                        st.session_state[f"chk_{oid}"] = select_all_state

                # Seçim Helperi
                def get_selected_ids():
                    selected = []
                    for oid in orders_df['id']:
                        if st.session_state.get(f"chk_{oid}", False):
                            selected.append(oid)
                    return selected

                # --- PANEL BAŞLIĞI (Hamısını Seç & Sil) ---
                col_master, col_del_top = st.columns([2, 2])
                
                with col_master:
                    # MASTER CHECKBOX
                    st.checkbox("☑️ Hamısını Seç", key="master_select", on_change=toggle_select_all)
                
                with col_del_top:
                    if st.button("🗑️ Seçilənləri Sil (Üst)", type="primary"):
                        ids_to_del = get_selected_ids()
                        if ids_to_del:
                            st.session_state['confirm_del_ids'] = ids_to_del
                        else:
                            st.toast("Heç nə seçilməyib!")

            # ------------------------------------------------------------------
            # MALLARIN SİYAHISI
            # ------------------------------------------------------------------
            for index, row in orders_df.iterrows():
                oid = row['id']
                prod = row['product_name']
                qty = row['qty']
                unit = row.get('unit', '')
                status = row['status']
                winner_db = row.get('winner', '')
                try:
                    time_cr = pd.to_datetime(row['created_at']).strftime("%Y-%m-%d %H:%M")
                except:
                    time_cr = str(row['created_at'])[:16]
                
                # Admin üçün Checkbox
                if user == "Admin":
                    col_check, col_card = st.columns([0.5, 9.5])
                    with col_check:
                        # Burada default value yox, key vasitəsilə state idarə olunur
                        st.checkbox("", key=f"chk_{oid}")
                else:
                    col_card = st.container()

                with col_card:
                    border_color = True
                    if status == 'Təsdiqlənib':
                        st.error(f"⚠️ Bu mal satılıb! Alıcı: **{winner_db}**")
                    
                    with st.container(border=border_color):
                        col_l, col_m, col_r = st.columns([2, 2, 3])
                        
                        with col_l:
                            st.markdown(f"### 📦 {prod}")
                            st.write(f"**Tələb:** {qty} {unit}")
                            st.caption(f"Yaradılıb: {time_cr}")
                            if status == 'Təsdiqlənib':
                                st.caption(f"🔒 Status: {winner_db} təsdiqlədi")
                        
                        with col_m:
                            if status == 'Axtarışda':
                                if user == "Admin":
                                    st.info("👁️ (İzləmə Rejimi)")
                                else:
                                    st.write("💰 **Təklifiniz:**")
                                    my_val = 0.0
                                    if not all_bids_df.empty:
                                        my_bid = all_bids_df[(all_bids_df['order_id'] == oid) & (all_bids_df['user'] == user)]
                                        if not my_bid.empty:
                                            my_val = my_bid.iloc[-1]['price']
                                    
                                    new_price = st.number_input("Qiymət (AZN)", value=float(my_val), step=1.0, key=f"inp_{oid}")
                                    if st.button("Göndər", key=f"btn_{oid}"):
                                        add_row("bids", {
                                            "order_id": oid,
                                            "user": user,
                                            "price": new_price,
                                            "timestamp": datetime.now().strftime("%H:%M:%S")
                                        })
                                        st.toast("Göndərildi!")
                                        time.sleep(0.5)
                                        st.rerun()
                            else:
                                st.warning(f"🔒 Satış Bağlandı. ({winner_db} aldı)")

                        with col_r:
                            st.write("📊 **Vəziyyət:**")
                            if not all_bids_df.empty:
                                relevant_bids = all_bids_df[all_bids_df['order_id'] == oid]
                                if not relevant_bids.empty:
                                    latest_bids = relevant_bids.sort_values('id').groupby('user').tail(1)
                                    sorted_bids = latest_bids.sort_values(by="price", ascending=True)
                                    best_bid = sorted_bids.iloc[0]
                                    best_user = best_bid['user']
                                    best_price = best_bid['price']
                                    
                                    st.dataframe(sorted_bids[['user', 'price']], hide_index=True)

                                    if status == 'Axtarışda':
                                        if user == "Admin":
                                            st.write(f"Ən yaxşı: **{best_user}**")
                                            if st.button(f"✅ Təsdiqlə ({best_user})", key=f"approve_{oid}", type="primary"):
                                                update_order_stage(oid, 'Təsdiqlənib', best_user, best_price)
                                                st.rerun()
                                        else:
                                            if user == best_user:
                                                st.success("🏆 Lidersiniz!")
                                            else:
                                                st.info(f"Lider: {best_user} ({best_price} AZN)")

                                    elif status == 'Təsdiqlənib':
                                        if user == winner_db:
                                            st.success("✅ Admin təsdiqlədi! Malı almalısınız.")
                                            if st.button("🛒 ALDIM", key=f"finish_{oid}", type="primary"):
                                                update_order_stage(oid, 'Tamamlandı', user, best_price)
                                                st.balloons()
                                                time.sleep(1)
                                                st.rerun()
                                        elif user == "Admin":
                                            st.info(f"⏳ {winner_db} alır...")
                                        else:
                                            st.error(f"⛔ {winner_db} alır.")
                                else:
                                    st.caption("Təklif yoxdur.")
                            else:
                                st.caption("Təklif yoxdur.")

            # ------------------------------------------------------------------
            # AŞAĞI SİL DÜYMƏSİ (YALNIZ ADMIN ÜÇÜN)
            # ------------------------------------------------------------------
            if user == "Admin":
                st.write("---")
                col_bot_del, _ = st.columns([2, 10])
                if col_bot_del.button("🗑️ Seçilənləri Sil (Alt)", type="primary"):
                    ids_to_del = get_selected_ids()
                    if ids_to_del:
                        st.session_state['confirm_del_ids'] = ids_to_del
                    else:
                        st.toast("Heç nə seçilməyib!")

                # SİLMƏ TƏSDİQ PƏNCƏRƏSİ
                if 'confirm_del_ids' in st.session_state:
                    ids = st.session_state['confirm_del_ids']
                    st.warning(f"⚠️ {len(ids)} ədəd malı silməyə əminsiniz?")
                    c_yes, c_no = st.columns(2)
                    if c_yes.button("✅ Bəli, SİL"):
                        delete_orders(ids)
                        st.success("Mallar silindi!")
                        del st.session_state['confirm_del_ids']
                        # Master select-i də söndürək
                        if 'master_select' in st.session_state:
                             st.session_state['master_select'] = False
                        time.sleep(1)
                        st.rerun()
                    if c_no.button("❌ Xeyr"):
                        del st.session_state['confirm_del_ids']
                        st.rerun()

    with tab2:
        st.subheader("Bitmiş Tenderlər")
        response = supabase.table("orders").select("*").eq("status", "Tamamlandı").execute()
        history_df = pd.DataFrame(response.data)
        
        if not history_df.empty:
            cols_to_show = ['product_name', 'qty', 'unit', 'winner', 'final_price', 'created_at']
            existing_cols = [c for c in cols_to_show if c in history_df.columns]
            st.table(history_df[existing_cols])
        else:
            st.write("Tarixçə boşdur.")

else:
    st.info("👈 Zəhmət olmasa giriş edin.")
