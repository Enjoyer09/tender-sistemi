import streamlit as st
import pandas as pd
import time
from datetime import datetime
import pytz
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

# --- BAKI VAXTI ---
def get_baku_time():
    baku_tz = pytz.timezone('Asia/Baku')
    return datetime.now(baku_tz)

# --- BAZA FUNKSİYALARI ---
def get_data(table_name):
    response = supabase.table(table_name).select("*").execute()
    df = pd.DataFrame(response.data)
    return df

def add_row(table_name, data_dict):
    supabase.table(table_name).insert(data_dict).execute()

def submit_bid(order_id, user, price):
    response = supabase.table("bids").select("*").eq("order_id", order_id).eq("user", user).execute()
    current_time = get_baku_time().strftime("%H:%M")
    if response.data:
        bid_id = response.data[0]['id']
        supabase.table("bids").update({"price": price, "timestamp": current_time}).eq("id", bid_id).execute()
        return "Yeniləndi"
    else:
        supabase.table("bids").insert({"order_id": order_id, "user": user, "price": price, "timestamp": current_time}).execute()
        return "Göndərildi"

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

def upload_image_to_supabase(file_obj, filename):
    try:
        bucket_name = "images"
        unique_name = f"{int(time.time())}_{filename}"
        file_bytes = file_obj.getvalue()
        supabase.storage.from_(bucket_name).upload(path=unique_name, file=file_bytes, file_options={"content-type": file_obj.type})
        public_url = supabase.storage.from_(bucket_name).get_public_url(unique_name)
        return public_url
    except Exception as e:
        st.error(f"Yükləmə xətası: {e}")
        return None

def update_order_image(order_id, image_url):
    supabase.table("orders").update({"image_url": image_url}).eq("id", order_id).execute()

# --- POPUP SİLMƏ ---
@st.dialog("⚠️ Silməni Təsdiqləyin")
def confirm_delete_modal(ids_to_delete):
    st.warning(f"Seçilmiş **{len(ids_to_delete)}** ədəd malı bazadan silmək istədiyinizə əminsiniz?")
    col1, col2 = st.columns(2)
    if col1.button("✅ Bəli, SİL", type="primary"):
        with st.spinner("Silinir..."):
            delete_orders(ids_to_delete)
        st.success("Silindi!")
        if 'master_select' in st.session_state: del st.session_state['master_select']
        for oid in ids_to_delete:
            key = f"chk_{oid}"
            if key in st.session_state: del st.session_state[key]
        time.sleep(1)
        st.rerun()
    if col2.button("❌ Ləğv et"):
        st.rerun()

# --- EXCEL ANALİZİ ---
def detect_header_row(df_preview):
    keywords = ['description', 'item', 'mal', 'ad', 'product', 'qty', 'quantity', 'say', 'amount', 'birim', 'sira', 'sıra']
    for idx, row in df_preview.iterrows():
        row_text = " ".join(row.astype(str)).lower()
        match_count = sum(1 for k in keywords if k in row_text)
        if match_count >= 2: return idx
    return 0

def smart_column_guesser(df):
    cols = df.columns.tolist()
    name_col_idx = 0
    for i, col in enumerate(cols):
        col_str = str(col).lower()
        if 'mal' in col_str or 'desc' in col_str or 'ad' in col_str or 'ürün' in col_str:
            name_col_idx = i; break
        if 'unnamed' in col_str and i == 1: name_col_idx = i
    qty_col_idx = 0
    for i, col in enumerate(cols):
        col_str = str(col).lower()
        if 'sipariş' in col_str or 'order' in col_str: qty_col_idx = i; break
        elif 'qty' in col_str or 'say' in col_str or 'quan' in col_str: qty_col_idx = i
    unit_col_idx = None
    for i, col in enumerate(cols):
        col_str = str(col).lower()
        if 'unit' in col_str or 'ölçü' in col_str or 'birim' in col_str: unit_col_idx = i; break
    return name_col_idx, qty_col_idx, unit_col_idx

# --- SESSİYA ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'current_user' not in st.session_state: st.session_state['current_user'] = None
# Bildiriş sistemi üçün yaddaş
if 'known_sold_ids' not in st.session_state: st.session_state['known_sold_ids'] = []

# ==========================================
# YAN MENYU
# ==========================================
with st.sidebar:
    st.title("🔐 Giriş Paneli")
    with st.expander("🆘 Admin (Şifrə Sıfırla)"):
        with st.form("admin_reset_form"):
            master_key_input = st.text_input("Master Key", type="password")
            if st.form_submit_button("Yoxla"):
                if master_key_input.strip() == "admin123":
                    st.session_state['admin_unlocked'] = True
                    st.success("Admin Girişi ✅")
                else: st.error("Səhv Master Key")
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
                    if st.form_submit_button("Qeydiyyatdan Keç"):
                        add_row("users", {"username": selected_user, "password": new_pass})
                        st.success("Hazırdır! İndi giriş edin.")
                        time.sleep(1); st.rerun()
            else:
                with st.form("login_form"):
                    password = st.text_input("Şifrənizi yazın", type="password")
                    if st.form_submit_button("Daxil Ol 🚀"):
                        real_pass = user_data[0]['password']
                        if str(real_pass).strip() == str(password).strip():
                            st.session_state['logged_in'] = True
                            st.session_state['current_user'] = selected_user
                            st.rerun()
                        else: st.error("Şifrə yanlışdır!")
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
    
    c1, c2 = st.columns([8, 2])
    c1.title(f"👤 {user} - Şəxsi Kabinet")
    with c2:
        if st.button("🔄 Yenilə", type="primary"): st.rerun()
        current_time_str = get_baku_time().strftime("%H:%M:%S")
        st.caption(f"🕒 Son yenilənmə: **{current_time_str}**")

    # Data Yüklənməsi
    response = supabase.table("orders").select("*").neq("status", "Tamamlandı").execute()
    orders_df = pd.DataFrame(response.data)
    if not orders_df.empty:
        orders_df = orders_df.sort_values(by="id", ascending=False)
        
        # --- NOTIFICATION SİSTEMİ (YENİ) ---
        # 1. Hazırda satılmış (Təsdiqlənib) olanları tapırıq
        sold_items = orders_df[orders_df['status'] == 'Təsdiqlənib']
        current_sold_ids = sold_items['id'].tolist()
        
        # 2. Əgər bu siyahıda TƏZƏ satılan varsa, bildiriş ver
        # (Yəni 'known_sold_ids' siyahısında olmayan bir ID varsa)
        if st.session_state['known_sold_ids']:
            for index, row in sold_items.iterrows():
                sid = row['id']
                if sid not in st.session_state['known_sold_ids']:
                    # YENİ QALİB TAPILDI!
                    winner_name = row['winner']
                    prod_name = row['product_name']
                    # TOAST MESAJI
                    st.toast(f"📢 DİQQƏT! **{prod_name}** məhsulunu **{winner_name}** aldı!", icon="✅")
        
        # 3. Yaddaşı yeniləyirik (İndiki halı yadda saxlayırıq)
        st.session_state['known_sold_ids'] = current_sold_ids

    # --- ADMIN PANELI ---
    if user == "Admin":
        st.info("🔧 Admin Paneli")
        with st.expander("📂 Excel-dən Yüklə (Smart)", expanded=False):
            uploaded_file = st.file_uploader("Fayl Seç", type=["xlsx", "xls", "csv"])
            header_idx = 0 
            if uploaded_file:
                try:
                    file_engine = 'openpyxl'
                    if uploaded_file.name.endswith('.xls'): file_engine = 'xlrd'
                    if uploaded_file.name.endswith('.csv'): df_preview = pd.read_csv(uploaded_file, header=None, nrows=25)
                    else: df_preview = pd.read_excel(uploaded_file, header=None, nrows=25, engine=file_engine)
                    
                    detected_idx = detect_header_row(df_preview)
                    c_h1, c_h2 = st.columns([3, 1])
                    c_h1.write(f"🤖 Sistem **{detected_idx}-ci** sətri başlıq hesab edir.")
                    header_idx = c_h2.number_input("Başlıq Sətri:", min_value=0, value=int(detected_idx), step=1)

                    if uploaded_file.name.endswith('.csv'): 
                        uploaded_file.seek(0)
                        df_final = pd.read_csv(uploaded_file, header=header_idx)
                    else: df_final = pd.read_excel(uploaded_file, header=header_idx, engine=file_engine)

                    new_cols = []
                    for i, col in enumerate(df_final.columns):
                        if "Unnamed" in str(col):
                            if not df_final.iloc[:, i].isnull().all(): new_cols.append(f"Adsız {i}")
                            else: new_cols.append(col)
                        else: new_cols.append(col)
                    df_final.columns = new_cols
                    st.dataframe(df_final.head(3), height=100)
                    cols = df_final.columns.tolist()
                    gn, gq, gu = smart_column_guesser(df_final)

                    c1, c2, c3 = st.columns(3)
                    name_col = c1.selectbox("Malın Adı:", cols, index=gn)
                    qty_col = c2.selectbox("Say:", cols, index=gq)
                    ud = 0
                    if gu is not None: ud = gu
                    unit_col = c3.selectbox("Ölçü:", ["-Yoxdur-"] + cols, index=ud+1 if gu is not None else 0)
                    
                    if st.button("Sistemə Yüklə 📥"):
                        new_orders = []
                        cnt = 0
                        ts = get_baku_time().strftime("%Y-%m-%d %H:%M:%S")
                        for idx, row in df_final.iterrows():
                            pval = str(row[name_col])
                            inv = ['nan', 'none', 'subtotal', 'total']
                            if pval and pval.lower() not in inv and pval.strip() != '':
                                try:
                                    rq = row[qty_col]
                                    qv = float(rq) if not pd.isna(rq) else 1.0
                                except: qv = 1.0
                                uv = ""
                                if unit_col != "-Yoxdur-":
                                    uv = str(row[unit_col])
                                    if uv.lower() == 'nan': uv = ""
                                new_orders.append({"product_name": pval, "qty": qv, "unit": uv, "status": "Axtarışda", "created_at": ts})
                                cnt += 1
                        if new_orders:
                            supabase.table("orders").insert(new_orders).execute()
                            st.success(f"✅ {cnt} ədəd yükləndi.")
                            time.sleep(1); st.rerun()
                except Exception as e: st.error(f"Xəta: {e}")

        with st.expander("➕ Tək Sifariş Yarat"):
            with st.form("add_single"):
                c1, c2, c3 = st.columns([3, 1, 1])
                p_name = c1.text_input("Malın Adı")
                p_qty = c2.number_input("Say", 1, 100)
                p_unit = c3.text_input("Ölçü", value="eded")
                if st.form_submit_button("Əlavə Et"):
                    ts = get_baku_time().strftime("%Y-%m-%d %H:%M:%S")
                    add_row("orders", {"product_name": p_name, "qty": p_qty, "unit": p_unit, "status": "Axtarışda", "created_at": ts})
                    st.toast("Əlavə olundu!")
                    st.rerun()
        st.divider()

    tab1, tab2 = st.tabs(["🔥 Aktiv Bazar", "📜 Tarixçə"])

    with tab1:
        if orders_df.empty:
            st.info("Aktiv sifariş yoxdur.")
        else:
            bids_resp = supabase.table("bids").select("*").execute()
            all_bids_df = pd.DataFrame(bids_resp.data)

            if user == "Admin":
                def toggle_select_all():
                    val = st.session_state.get('master_select', False)
                    for oid in orders_df['id']: st.session_state[f"chk_{oid}"] = val
                def get_selected_ids():
                    return [oid for oid in orders_df['id'] if st.session_state.get(f"chk_{oid}", False)]
                
                c_m, c_b = st.columns([2, 10])
                c_m.checkbox("☑️ Hamısını Seç", key="master_select", on_change=toggle_select_all)
                if c_b.button("🗑️ Seçilənləri Sil (Üst)", type="primary"):
                    ids = get_selected_ids()
                    if ids: confirm_delete_modal(ids)
                    else: st.toast("Seçim yoxdur")

            for index, row in orders_df.iterrows():
                oid = row['id']
                prod = row['product_name']
                qty = row['qty']
                unit = row.get('unit', '')
                status = row['status']
                winner = row.get('winner', '')
                img = row.get('image_url', None)
                try: t_cr = str(row['created_at'])[:16]
                except: t_cr = str(row['created_at'])

                if user == "Admin":
                    cc, cc2 = st.columns([0.5, 9.5])
                    cc.checkbox("", key=f"chk_{oid}")
                else: cc2 = st.container()

                with cc2:
                    if status == 'Təsdiqlənib': st.error(f"⚠️ Satılıb! Alıcı: {winner}")
                    with st.container(border=True):
                        c_l, c_m, c_r = st.columns([2, 2, 3])
                        with c_l:
                            st.markdown(f"### 📦 {prod}")
                            st.write(f"**Tələb:** {qty} {unit}")
                            st.caption(f"Tarix: {t_cr}")
                            if img: st.image(img, width=150)
                            if user == "Admin":
                                with st.popover("📷 Şəkil"):
                                    f = st.file_uploader(f"Upl {oid}", type=['png','jpg'], key=f"up_{oid}")
                                    if f and st.button("Yüklə", key=f"btn_up_{oid}"):
                                        with st.spinner("..."):
                                            u = upload_image_to_supabase(f, f.name)
                                            if u:
                                                update_order_image(oid, u)
                                                st.success("OK")
                                                time.sleep(1); st.rerun()
                        with c_m:
                            if status == 'Axtarışda':
                                if user == "Admin": st.info("👁️ İzləmə")
                                else:
                                    st.write("💰 **Təklif:**")
                                    mv = 0.0
                                    if not all_bids_df.empty:
                                        bm = all_bids_df[(all_bids_df['order_id']==oid) & (all_bids_df['user']==user)]
                                        if not bm.empty: mv = bm.iloc[0]['price']
                                    np = st.number_input("AZN", value=float(mv), step=1.0, key=f"in_{oid}", label_visibility="collapsed")
                                    if st.button("Təsdiqlə", key=f"b_{oid}"):
                                        msg = submit_bid(oid, user, np)
                                        st.toast(f"{msg}!")
                                        time.sleep(0.5); st.rerun()
                            else: st.warning("🔒 Bağlıdır")
                        with c_r:
                            st.write("📊 **Vəziyyət:**")
                            if not all_bids_df.empty:
                                rb = all_bids_df[all_bids_df['order_id']==oid]
                                if not rb.empty:
                                    best = rb.sort_values(by="price").iloc[0]
                                    bu, bp = best['user'], best['price']
                                    st.write(f"🥇 **{bu}** - {bp} AZN")
                                    if status == 'Axtarışda':
                                        if user == "Admin":
                                            if st.button(f"✅ Təsdiqlə ({bu})", key=f"ap_{oid}", type="primary"):
                                                update_order_stage(oid, 'Təsdiqlənib', bu, bp)
                                                st.rerun()
                                        elif user == bu: st.success("🏆 Lidersiniz!")
                                    elif status == 'Təsdiqlənib':
                                        if user == winner:
                                            st.success("✅ Sizindir!")
                                            if st.button("🛒 ALDIM", key=f"fn_{oid}", type="primary"):
                                                update_order_stage(oid, 'Tamamlandı', user, bp)
                                                st.balloons(); time.sleep(1); st.rerun()
                                        else: st.error(f"⛔ {winner} aldı")
                                else: st.caption("Təklif yoxdur")
                            else: st.caption("Təklif yoxdur")

            if user == "Admin":
                st.write("---")
                if st.button("🗑️ Seçilənləri Sil (Alt)", type="primary"):
                    ids = get_selected_ids()
                    if ids: confirm_delete_modal(ids)
                    else: st.toast("Seçim yoxdur")

    with tab2:
        st.subheader("Bitmiş Tenderlər")
        response = supabase.table("orders").select("*").eq("status", "Tamamlandı").execute()
        hdf = pd.DataFrame(response.data)
        if not hdf.empty:
            cols = ['product_name', 'qty', 'unit', 'winner', 'final_price', 'created_at']
            ec = [c for c in cols if c in hdf.columns]
            st.table(hdf[ec])
        else: st.write("Tarixçə boşdur.")
else:
    st.info("👈 Giriş edin")
