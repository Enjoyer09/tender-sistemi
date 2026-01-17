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

def submit_bid(order_id, user, price):
    """Qiyməti yeniləyir və ya əlavə edir"""
    response = supabase.table("bids").select("*").eq("order_id", order_id).eq("user", user).execute()
    current_time = datetime.now().strftime("%H:%M")
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
    st.write("Bu əməliyyat geri qaytarıla bilməz.")
    col1, col2 = st.columns(2)
    if col1.button("✅ Bəli, SİL", type="primary"):
        with st.spinner("Silinir..."):
            delete_orders(ids_to_delete)
        st.success("Mallar uğurla silindi!")
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
        if match_count >= 2:
            return idx
    return 0

def smart_column_guesser(df):
    cols = df.columns.tolist()
    name_col_idx = 0
    for i, col in enumerate(cols):
        col_str = str(col).lower()
        if 'mal' in col_str or 'desc' in col_str or 'ad' in col_str or 'ürün' in col_str:
            name_col_idx = i
            break
        if 'unnamed' in col_str and i == 1:
            name_col_idx = i
            
    qty_col_idx = 0
    for i, col in enumerate(cols):
        col_str = str(col).lower()
        if 'sipariş' in col_str or 'order' in col_str:
            qty_col_idx = i
            break
        elif 'qty' in col_str or 'say' in col_str or 'quan' in col_str or 'miktar' in col_str:
            qty_col_idx = i
    
    unit_col_idx = None
    for i, col in enumerate(cols):
        col_str = str(col).lower()
        if 'unit' in col_str or 'ölçü' in col_str or 'birim' in col_str or 'vahid' in col_str:
            unit_col_idx = i
            break
    return name_col_idx, qty_col_idx, unit_col_idx

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
    
    # --- YENİ YER: BAŞLIQ VƏ YENİLƏ DÜYMƏSİ ƏN YUXARIDA ---
    c1, c2 = st.columns([8, 2])
    c1.title(f"👤 {user} - Şəxsi Kabinet")
    if c2.button("🔄 Yenilə", type="primary"):
        st.rerun()

    # Bazadan oxumaq
    response = supabase.table("orders").select("*").neq("status", "Tamamlandı").execute()
    orders_df = pd.DataFrame(response.data)
    if not orders_df.empty:
        orders_df = orders_df.sort_values(by="id", ascending=False)
    
    # --- ADMIN PANELI ---
    if user == "Admin":
        st.info("🔧 Admin Paneli")
        
        # EXCEL YÜKLƏMƏ
        with st.expander("📂 Excel-dən Yüklə (Smart)", expanded=False):
            uploaded_file = st.file_uploader("Fayl Seç", type=["xlsx", "xls", "csv"])
            header_idx = 0 
            if uploaded_file:
                try:
                    file_engine = 'openpyxl'
                    if uploaded_file.name.endswith('.xls'): file_engine = 'xlrd'
                    if uploaded_file.name.endswith('.csv'):
                        df_preview = pd.read_csv(uploaded_file, header=None, nrows=25)
                    else:
                        df_preview = pd.read_excel(uploaded_file, header=None, nrows=25, engine=file_engine)
                    
                    detected_idx = detect_header_row(df_preview)
                    c_head1, c_head2 = st.columns([3, 1])
                    c_head1.write(f"🤖 Sistem cədvəlin **{detected_idx}-ci** sətirdən başladığını düşünür.")
                    header_idx = c_head2.number_input("Başlıq Sətri:", min_value=0, value=int(detected_idx), step=1)

                    if uploaded_file.name.endswith('.csv'):
                        uploaded_file.seek(0)
                        df_final = pd.read_csv(uploaded_file, header=header_idx)
                    else:
                        df_final = pd.read_excel(uploaded_file, header=header_idx, engine=file_engine)

                    new_columns = []
                    for i, col in enumerate(df_final.columns):
                        if "Unnamed" in str(col):
                            if not df_final.iloc[:, i].isnull().all():
                                new_columns.append(f"Adsız Sütun {i} (Məlumat var)")
                            else:
                                new_columns.append(col)
                        else:
                            new_columns.append(col)
                    df_final.columns = new_columns
                    st.dataframe(df_final.head(3), height=100)
                    cols = df_final.columns.tolist()
                    guess_name, guess_qty, guess_unit = smart_column_guesser(df_final)

                    c1, c2, c3 = st.columns(3)
                    name_col = c1.selectbox("Malın Adı:", cols, index=guess_name)
                    qty_col = c2.selectbox("Say:", cols, index=guess_qty)
                    unit_default = 0
                    if guess_unit is not None: unit_default = guess_unit
                    unit_col = c3.selectbox("Ölçü:", ["-Yoxdur-"] + cols, index=unit_default + 1 if guess_unit is not None else 0)
                    
                    st.info(f"👀 Nümunə: **{df_final[name_col].iloc[0]}** | Say: **{df_final[qty_col].iloc[0]}**")

                    if st.button("Sistemə Yüklə 📥"):
                        new_orders_list = []
                        count = 0
                        for index, row in df_final.iterrows():
                            prod_val = str(row[name_col])
                            invalid_words = ['nan', 'none', 'subtotal', 'total', 'grand total', 'talep eden', 'onay']
                            if prod_val and prod_val.lower() not in invalid_words and prod_val.strip() != '':
                                try:
                                    raw_qty = row[qty_col]
                                    if pd.isna(raw_qty): q_val = 1.0
                                    else: q_val = float(raw_qty)
                                except: q_val = 1.0
                                u_val = ""
                                if unit_col != "-Yoxdur-":
                                    u_val = str(row[unit_col])
                                    if u_val.lower() == 'nan': u_val = ""
                                new_orders_list.append({
                                    "product_name": prod_val, "qty": q_val, "unit": u_val, "status": "Axtarışda",
                                })
                                count += 1
                        if new_orders_list:
                            supabase.table("orders").insert(new_orders_list).execute()
                            st.success(f"✅ {count} ədəd mal bazaya yükləndi.")
                            time.sleep(1)
                            st.rerun()
                except Exception as e:
                    st.error(f"Xəta: {e}")

        # TƏK SİFARİŞ
        with st.expander("➕ Tək Sifariş Yarat"):
            with st.form("add_single"):
                c1, c2, c3 = st.columns([3, 1, 1])
                p_name = c1.text_input("Malın Adı")
                p_qty = c2.number_input("Say", 1, 100)
                p_unit = c3.text_input("Ölçü", value="eded")
                if st.form_submit_button("Əlavə Et"):
                    add_row("orders", {"product_name": p_name, "qty": p_qty, "unit": p_unit, "status": "Axtarışda"})
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
                    for oid in orders_df['id']:
                        st.session_state[f"chk_{oid}"] = val
                def get_selected_ids():
                    selected = []
                    for oid in orders_df['id']:
                        if st.session_state.get(f"chk_{oid}", False):
                            selected.append(oid)
                    return selected
                c_master, c_btn = st.columns([2, 10])
                c_master.checkbox("☑️ Hamısını Seç", key="master_select", on_change=toggle_select_all)
                if c_btn.button("🗑️ Seçilənləri Sil (Üst)", type="primary"):
                    ids_to_del = get_selected_ids()
                    if ids_to_del: confirm_delete_modal(ids_to_del)
                    else: st.toast("Seçim edilməyib!")

            for index, row in orders_df.iterrows():
                oid = row['id']
                prod = row['product_name']
                qty = row['qty']
                unit = row.get('unit', '')
                status = row['status']
                winner_db = row.get('winner', '')
                image_url = row.get('image_url', None)
                try: time_cr = pd.to_datetime(row['created_at']).strftime("%Y-%m-%d %H:%M")
                except: time_cr = str(row['created_at'])[:16]
                
                if user == "Admin":
                    col_chk, col_content = st.columns([0.5, 9.5])
                    col_chk.checkbox("", key=f"chk_{oid}")
                else:
                    col_content = st.container()

                with col_content:
                    border_color = True
                    if status == 'Təsdiqlənib': st.error(f"⚠️ Satılıb! Alıcı: {winner_db}")
                    
                    with st.container(border=border_color):
                        c_l, c_m, c_r = st.columns([2, 2, 3])
                        
                        # SOL - MƏLUMAT
                        with c_l:
                            st.markdown(f"### 📦 {prod}")
                            st.write(f"**Tələb:** {qty} {unit}")
                            st.caption(f"Tarix: {time_cr}")
                            if image_url: st.image(image_url, width=150)
                            if user == "Admin":
                                with st.popover("📷 Şəkil Yüklə"):
                                    img_file = st.file_uploader(f"Şəkil ({oid})", type=['png','jpg','jpeg'], key=f"upl_{oid}")
                                    if img_file and st.button("Yüklə", key=f"save_img_{oid}"):
                                        with st.spinner("Yüklənir..."):
                                            url = upload_image_to_supabase(img_file, img_file.name)
                                            if url:
                                                update_order_image(oid, url)
                                                st.success("Yükləndi!")
                                                time.sleep(1)
                                                st.rerun()
                            if status == 'Təsdiqlənib': st.caption(f"🔒 Təsdiqləyən: Admin")
                        
                        # ORTA - QİYMƏT
                        with c_m:
                            if status == 'Axtarışda':
                                if user == "Admin":
                                    st.info("👁️ (İzləmə)")
                                else:
                                    st.write("💰 **Təklifiniz:**")
                                    my_val = 0.0
                                    if not all_bids_df.empty:
                                        bid_match = all_bids_df[(all_bids_df['order_id'] == oid) & (all_bids_df['user'] == user)]
                                        if not bid_match.empty:
                                            my_val = bid_match.iloc[0]['price']
                                    
                                    new_price = st.number_input("Qiymət", value=float(my_val), step=1.0, key=f"inp_{oid}")
                                    if st.button("Təsdiqlə / Yenilə", key=f"btn_{oid}"):
                                        msg = submit_bid(oid, user, new_price)
                                        st.toast(f"{msg}!")
                                        time.sleep(0.5)
                                        st.rerun()
                            else:
                                st.warning("🔒 Satış Bağlandı.")

                        # SAĞ - NƏTİCƏ
                        with c_r:
                            st.write("📊 **Vəziyyət:**")
                            if not all_bids_df.empty:
                                rel_bids = all_bids_df[all_bids_df['order_id'] == oid]
                                if not rel_bids.empty:
                                    best_bid = rel_bids.sort_values(by="price", ascending=True).iloc[0]
                                    best_u = best_bid['user']
                                    best_p = best_bid['price']
                                    st.write(f"🥇 **{best_u}** - {best_p} AZN")
                                    if status == 'Axtarışda':
                                        if user == "Admin":
                                            if st.button(f"✅ Təsdiqlə ({best_u})", key=f"app_{oid}", type="primary"):
                                                update_order_stage(oid, 'Təsdiqlənib', best_u, best_p)
                                                st.rerun()
                                        elif user == best_u:
                                            st.success("🏆 Lidersiniz!")
                                    elif status == 'Təsdiqlənib':
                                        if user == winner_db:
                                            st.success("✅ Təsdiqləndi!")
                                            if st.button("🛒 ALDIM", key=f"fin_{oid}", type="primary"):
                                                update_order_stage(oid, 'Tamamlandı', user, best_p)
                                                st.balloons()
                                                time.sleep(1)
                                                st.rerun()
                                        else: st.error(f"⛔ {winner_db} alır.")
                                else: st.caption("Təklif yoxdur.")
                            else: st.caption("Təklif yoxdur.")

            if user == "Admin":
                st.write("---")
                if st.button("🗑️ Seçilənləri Sil (Alt)", type="primary"):
                    ids_to_del = get_selected_ids()
                    if ids_to_del: confirm_delete_modal(ids_to_del)
                    else: st.toast("Seçim edilməyib!")

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
