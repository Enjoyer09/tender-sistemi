import streamlit as st
import pandas as pd
import time
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- SƏHİFƏ TƏNZİMLƏMƏLƏRİ ---
st.set_page_config(page_title="Global Tender Sistemi", layout="wide")

# --- GOOGLE SHEETS BAZA SİSTEMİ ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data(worksheet):
    try:
        return conn.read(worksheet=worksheet, ttl=0)
    except:
        return pd.DataFrame()

def add_rows_bulk(worksheet, new_data_list):
    df = get_data(worksheet)
    new_df = pd.DataFrame(new_data_list)
    updated_df = pd.concat([df, new_df], ignore_index=True)
    conn.update(worksheet=worksheet, data=updated_df)

def add_row(worksheet, new_data_dict):
    add_rows_bulk(worksheet, [new_data_dict])

# --- YENİ: Statusu dəyişmək üçün universal funksiya ---
def update_order_stage(order_id, new_status, winner, price):
    df = get_data("orders")
    mask = df['id'] == order_id
    if mask.any():
        df.loc[mask, 'status'] = new_status
        df.loc[mask, 'winner'] = winner
        df.loc[mask, 'final_price'] = price
        conn.update(worksheet="orders", data=df)

def update_user_password(username, new_password):
    df = get_data("users")
    mask = df['username'] == username
    if mask.any():
        df.loc[mask, 'password'] = new_password
        conn.update(worksheet="users", data=df)
    else:
        pass 

def find_column_by_keyword(columns, keywords):
    for col in columns:
        for key in keywords:
            if key.lower() in str(col).lower():
                return col
    return None

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

    # --- ŞİFRƏ BƏRPASI ---
    with st.expander("🆘 Admin (Şifrə Sıfırla)"):
        master_key_input = st.text_input("Master Key", type="password", key="mk_inp")
        if master_key_input.strip() == "admin123":
            st.success("Admin Girişi ✅")
            reset_user = st.selectbox("İşçi seçin", ["Admin", "Anar", "Samir", "Vüsal", "Orxan", "Elnur"])
            new_pass_admin = st.text_input("Yeni şifrə", key="rst_pass")
            if st.button("Şifrəni Dəyiş"):
                users_df = get_data("users")
                if not users_df.empty and reset_user in users_df['username'].values:
                    update_user_password(reset_user, new_pass_admin)
                    st.success("Yeniləndi!")
                else:
                    add_row("users", {"username": reset_user, "password": new_pass_admin})
                    st.success("İstifadəçi yaradıldı!")

    st.divider()

    # --- GİRİŞ ---
    if not st.session_state['logged_in']:
        users_list = ["Seçin...", "Admin", "Anar", "Samir", "Vüsal", "Orxan", "Elnur"]
        selected_user = st.selectbox("İşçi Adı", users_list)

        if selected_user != "Seçin...":
            users_df = get_data("users")
            user_exist = False
            if not users_df.empty and selected_user in users_df['username'].values:
                user_exist = True
            
            if not user_exist:
                st.warning("İlk girişinizdir.")
                new_pass = st.text_input("Yeni Şifrə Təyin Et", type="password")
                if st.button("Qeydiyyatdan Keç"):
                    add_row("users", {"username": selected_user, "password": new_pass})
                    st.success("Hazırdır! Daxil olun.")
                    time.sleep(1)
                    st.rerun()
            else:
                password = st.text_input("Şifrənizi yazın", type="password")
                if st.button("Daxil Ol 🚀"):
                    user_record = users_df[users_df['username'] == selected_user].iloc[0]
                    if str(user_record['password']).strip() == str(password).strip():
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
    
    # --- ADMIN PANELI ---
    if user == "Admin":
        st.info("🔧 Admin Paneli")
        
        with st.expander("📂 Excel-dən Yüklə (Ağıllı Rejim)", expanded=True):
            uploaded_file = st.file_uploader("Fayl Seç", type=["xlsx", "xls", "csv"])
            header_row_idx = st.number_input("Başlıq neçənci sətirdədir? (0 = İlk sətir)", min_value=0, value=0)
            
            if uploaded_file:
                try:
                    if uploaded_file.name.endswith('.csv'):
                        df_upload = pd.read_csv(uploaded_file, header=header_row_idx)
                    else:
                        df_upload = pd.read_excel(uploaded_file, header=header_row_idx)
                    
                    st.dataframe(df_upload.head(3), height=100)
                    cols = df_upload.columns.tolist()
                    
                    def_name = find_column_by_keyword(cols, ["item", "description", "mal", "product", "ad"])
                    def_qty = find_column_by_keyword(cols, ["qty", "quantity", "say", "amount", "miqdar"])
                    def_unit = find_column_by_keyword(cols, ["unit", "measure", "vahid", "olcu"])

                    c1, c2, c3 = st.columns(3)
                    name_col = c1.selectbox("Malın Adı:", cols, index=cols.index(def_name) if def_name else 0)
                    qty_col = c2.selectbox("Say:", cols, index=cols.index(def_qty) if def_qty else 0)
                    unit_col = c3.selectbox("Ölçü (Varsa):", ["-Yoxdur-"] + cols, index=cols.index(def_unit)+1 if def_unit else 0)
                    
                    if st.button("Sistemə Yüklə 📥"):
                        orders_df = get_data("orders")
                        start_id = 1
                        if not orders_df.empty and 'id' in orders_df.columns:
                            clean_ids = pd.to_numeric(orders_df['id'], errors='coerce').fillna(0)
                            start_id = int(clean_ids.max()) + 1
                        
                        new_orders_list = []
                        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
                        
                        count = 0
                        for index, row in df_upload.iterrows():
                            prod_val = str(row[name_col])
                            if prod_val and prod_val.lower() not in ['nan', 'none', 'subtotal'] and prod_val.strip() != '':
                                try:
                                    q_val = int(float(row[qty_col]))
                                except:
                                    q_val = 1
                                
                                u_val = ""
                                if unit_col != "-Yoxdur-":
                                    u_val = str(row[unit_col])
                                    if u_val.lower() == 'nan': u_val = ""

                                new_orders_list.append({
                                    "id": start_id + count,
                                    "product_name": prod_val,
                                    "qty": q_val,
                                    "unit": u_val,
                                    "status": "Axtarışda",
                                    "winner": "",
                                    "final_price": 0.0,
                                    "created_at": current_time
                                })
                                count += 1
                        
                        if new_orders_list:
                            add_rows_bulk("orders", new_orders_list)
                            st.success(f"{count} ədəd mal yükləndi!")
                            time.sleep(2)
                            st.rerun()
                except Exception as e:
                    st.error(f"Xəta: {e}")

        with st.expander("➕ Tək Sifariş Yarat"):
            with st.form("add_single"):
                c1, c2, c3 = st.columns([3, 1, 1])
                p_name = c1.text_input("Malın Adı")
                p_qty = c2.number_input("Say", 1, 100)
                p_unit = c3.text_input("Ölçü", value="eded")
                
                if st.form_submit_button("Əlavə Et"):
                    orders_df = get_data("orders")
                    new_id = 1
                    if not orders_df.empty and 'id' in orders_df.columns:
                        clean_ids = pd.to_numeric(orders_df['id'], errors='coerce').fillna(0)
                        new_id = int(clean_ids.max()) + 1
                    
                    add_row("orders", {
                        "id": new_id,
                        "product_name": p_name,
                        "qty": p_qty,
                        "unit": p_unit,
                        "status": "Axtarışda",
                        "winner": "",
                        "final_price": 0.0,
                        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
                    })
                    st.toast("Əlavə olundu!")
                    st.rerun()
        st.divider()

    # --- ÜMUMİ İŞÇİ EKRANI ---
    c1, c2 = st.columns([8, 2])
    c1.title(f"👤 {user} - Şəxsi Kabinet")
    if c2.button("🔄 Yenilə"):
        st.rerun()

    tab1, tab2 = st.tabs(["🔥 Aktiv Bazar", "📜 Tarixçə"])

    with tab1:
        orders_df = get_data("orders")
        
        # Həm 'Axtarışda' olanları, həm də 'Təsdiqlənib' olanları göstər
        if orders_df.empty or 'status' not in orders_df.columns:
            st.info("Bazada mal yoxdur.")
            active_orders = pd.DataFrame()
        else:
            # Statusu 'Tamamlandı' OLMAYAN hər şeyi gətir
            active_orders = orders_df[orders_df['status'].isin(['Axtarışda', 'Təsdiqlənib'])]

        if active_orders.empty:
            st.info("Aktiv sifariş yoxdur.")
        else:
            active_orders = active_orders.sort_values(by="id", ascending=False)
            
            for index, row in active_orders.iterrows():
                oid = row['id']
                prod = row['product_name']
                qty = row['qty']
                unit = row.get('unit', '')
                status = row['status']
                winner_db = row.get('winner', '')
                time_cr = row['created_at']
                
                # Kart Dizaynı - Rəngləri fərqləndirək
                border_color = True
                if status == 'Təsdiqlənib':
                    st.warning(f"⚠️ DİQQƏT! Bu malın satınalınması təsdiqlənib. ({winner_db} alır)")
                
                with st.container(border=border_color):
                    col_l, col_m, col_r = st.columns([2, 2, 3])
                    
                    # --- SOL HİSSƏ ---
                    with col_l:
                        st.markdown(f"### 📦 {prod}")
                        st.write(f"**Tələb:** {qty} {unit}")
                        st.caption(f"Yaradılıb: {time_cr}")
                        if status == 'Təsdiqlənib':
                            st.caption(f"🔴 Status: Alınma prosesində ({winner_db})")
                    
                    # --- ORTA HİSSƏ (QİYMƏT YAZMA) ---
                    with col_m:
                        if status == 'Axtarışda':
                            st.write("💰 **Təklifiniz:**")
                            bids_df = get_data("bids")
                            my_val = 0.0
                            if not bids_df.empty:
                                my_bid = bids_df[(bids_df['order_id'] == oid) & (bids_df['user'] == user)]
                                if not my_bid.empty:
                                    my_val = my_bid.iloc[-1]['price']
                            
                            new_price = st.number_input("Qiymət (AZN)", value=float(my_val), step=1.0, key=f"inp_{oid}")
                            
                            if st.button("Göndər", key=f"btn_{oid}"):
                                new_bid_id = 1
                                if not bids_df.empty and 'id' in bids_df.columns:
                                    clean_ids = pd.to_numeric(bids_df['id'], errors='coerce').fillna(0)
                                    new_bid_id = int(clean_ids.max()) + 1

                                add_row("bids", {
                                    "id": new_bid_id,
                                    "order_id": oid,
                                    "user": user,
                                    "price": new_price,
                                    "timestamp": datetime.now().strftime("%H:%M:%S")
                                })
                                st.toast("Göndərildi!")
                                time.sleep(1)
                                st.rerun()
                        else:
                            # Təsdiqlənib statusundadırsa, qiymət yazmaq olmaz
                            st.info("🚫 Artıq təklif qəbul olunmur.")

                    # --- SAĞ HİSSƏ (NƏTİCƏLƏR VƏ QƏRAR) ---
                    with col_r:
                        st.write("📊 **Vəziyyət:**")
                        bids_df = get_data("bids")
                        
                        if not bids_df.empty:
                            relevant_bids = bids_df[bids_df['order_id'] == oid]
                            if not relevant_bids.empty:
                                latest_bids = relevant_bids.sort_values('id').groupby('user').tail(1)
                                sorted_bids = latest_bids.sort_values(by="price", ascending=True)
                                
                                best_bid = sorted_bids.iloc[0]
                                best_user = best_bid['user']
                                best_price = best_bid['price']
                                
                                st.dataframe(sorted_bids[['user', 'price']], hide_index=True)

                                # --------------------------------------------
                                # MƏNTİQ DƏYİŞİKLİYİ BURADADIR
                                # --------------------------------------------
                                
                                # A. ƏGƏR STATUS 'AXTARIŞDA'DIRSA
                                if status == 'Axtarışda':
                                    if user == "Admin":
                                        # Admin yalnız təsdiq edə bilər (Özü ala bilməz)
                                        st.write(f"Lider: **{best_user}**")
                                        if st.button(f"✅ Təsdiqlə ({best_user} alsın)", key=f"approve_{oid}", type="primary"):
                                            update_order_stage(oid, 'Təsdiqlənib', best_user, best_price)
                                            st.rerun()
                                    else:
                                        # İşçilər sadəcə lideri görür
                                        if user == best_user:
                                            st.success("🏆 Hazırda Lidersiniz! Admin təsdiqini gözləyin.")
                                        else:
                                            st.warning(f"Lider: {best_user} ({best_price} AZN)")

                                # B. ƏGƏR STATUS 'TƏSDİQLƏNİB'DİRSƏ
                                elif status == 'Təsdiqlənib':
                                    if user == winner_db:
                                        # Yalnız QALİB İŞÇİ "Al" düyməsini görür
                                        st.success("✅ Admin təsdiqlədi! Malı almalısınız.")
                                        if st.button("🛒 ALDIM (Prosesi Bitir)", key=f"finish_{oid}", type="primary"):
                                            update_order_stage(oid, 'Tamamlandı', user, best_price)
                                            st.balloons()
                                            time.sleep(2)
                                            st.rerun()
                                    else:
                                        # Digər işçilər və Admin
                                        st.error(f"⛔ Bu malı {winner_db} alır.")
                                        
                            else:
                                st.caption("Təklif yoxdur.")
                        else:
                            st.caption("Təklif yoxdur.")

    with tab2:
        st.subheader("Bitmiş Tenderlər")
        orders_df = get_data("orders")
        if not orders_df.empty and 'status' in orders_df.columns:
            history_df = orders_df[orders_df['status'] == 'Tamamlandı']
            if not history_df.empty:
                cols_to_show = ['product_name', 'qty', 'winner', 'final_price', 'created_at']
                if 'unit' in history_df.columns:
                    cols_to_show.insert(2, 'unit')
                st.table(history_df[cols_to_show])
            else:
                st.write("Tarixçə boşdur.")
        else:
            st.write("Baza boşdur.")

else:
    st.info("👈 Zəhmət olmasa giriş edin.")
