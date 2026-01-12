import streamlit as st
import pandas as pd
import time
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# SƏHİFƏ TƏNZİMLƏMƏLƏRİ
st.set_page_config(page_title="Global Tender Sistemi", layout="wide")

# --- GOOGLE SHEETS BAZA SİSTEMİ ---
# Bazaya qoşulmaq üçün connection yaradiriq
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data(worksheet):
    """Məlumatları cədvəldən oxuyur"""
    # Cache istifadə etmirik ki, məlumatlar həmişə təzə olsun (ttl=0)
    return conn.read(worksheet=worksheet, ttl=0)

def add_row(worksheet, new_data_dict):
    """Yeni sətir əlavə edir"""
    df = get_data(worksheet)
    new_df = pd.DataFrame([new_data_dict])
    updated_df = pd.concat([df, new_df], ignore_index=True)
    conn.update(worksheet=worksheet, data=updated_df)

def update_order_status(order_id, winner, price):
    """Sifarişi tamamlayır (Update funksiyası)"""
    df = get_data("orders")
    # Pandas ilə sətri tapıb dəyişirik
    mask = df['id'] == order_id
    if mask.any():
        df.loc[mask, 'status'] = 'Tamamlandı'
        df.loc[mask, 'winner'] = winner
        df.loc[mask, 'final_price'] = price
        conn.update(worksheet="orders", data=df)

def update_user_password(username, new_password):
    """Şifrəni yeniləyir"""
    df = get_data("users")
    mask = df['username'] == username
    if mask.any():
        df.loc[mask, 'password'] = new_password
        conn.update(worksheet="users", data=df)
    else:
        # Əgər yoxdursa yeni istifadəçi kimi əlavə et (Admin panel üçün)
        pass 

# SESSİYA (Login yaddaşı)
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'current_user' not in st.session_state:
    st.session_state['current_user'] = None

# ==========================================
# YAN MENYU - LOGIN & ADMIN
# ==========================================
with st.sidebar:
    st.title("🔐 Giriş Paneli")

    # --- ADMIN PANELI (Şifrə Bərpası) ---
    with st.expander("🆘 Admin (Şifrə Sıfırla)"):
        master_key = st.text_input("Master Key", type="password")
        if master_key == "admin123":
            st.success("Admin Girişi ✅")
            reset_user = st.selectbox("İşçi seçin", ["Anar", "Samir", "Vüsal", "Orxan", "Elnur"])
            new_pass_admin = st.text_input("Yeni şifrə", key="rst_pass")
            if st.button("Şifrəni Dəyiş"):
                # İstifadəçi varmı?
                users_df = get_data("users")
                if reset_user in users_df['username'].values:
                    update_user_password(reset_user, new_pass_admin)
                    st.success("Yeniləndi!")
                else:
                    # Yoxdursa yaradırıq
                    add_row("users", {"username": reset_user, "password": new_pass_admin})
                    st.success("İstifadəçi yaradıldı!")

    st.divider()

    # --- STANDART GİRİŞ ---
    if not st.session_state['logged_in']:
        users_list = ["Seçin...", "Admin", "Anar", "Samir", "Vüsal", "Orxan", "Elnur"]
        selected_user = st.selectbox("İşçi Adı", users_list)

        if selected_user != "Seçin...":
            users_df = get_data("users")
            
            # İstifadəçi bazada varmı?
            user_record = users_df[users_df['username'] == selected_user]
            
            if user_record.empty:
                st.warning("İlk girişinizdir. Qeydiyyat olun.")
                new_pass = st.text_input("Yeni Şifrə", type="password")
                if st.button("Qeydiyyatdan Keç"):
                    if new_pass:
                        add_row("users", {"username": selected_user, "password": new_pass})
                        st.success("Hazırdır! İndi daxil olun.")
                        st.rerun()
            else:
                password = st.text_input("Şifrəni yazın", type="password")
                if st.button("Daxil Ol 🚀"):
                    real_pass = user_record.iloc[0]['password']
                    # Pandas bəzən rəqəmi int/float kimi oxuyur, ona görə str() edirik
                    if str(real_pass) == str(password):
                        st.session_state['logged_in'] = True
                        st.session_state['current_user'] = selected_user
                        st.rerun()
                    else:
                        st.error("Şifrə səhvdir!")
    else:
        st.success(f"Xoş gəldin, **{st.session_state['current_user']}**")
        if st.button("Çıxış Et"):
            st.session_state['logged_in'] = False
            st.session_state['current_user'] = None
            st.rerun()
        
        st.divider()
        st.subheader("Yeni Sifariş")
        with st.form("add_order_form"):
            p_name = st.text_input("Malın Adı")
            p_qty = st.number_input("Say", 1, 100)
            if st.form_submit_button("Sistemə Vur"):
                # ID yaratmaq üçün mövcud say + 1
                orders_df = get_data("orders")
                new_id = 1
                if not orders_df.empty:
                    # 'id' sütununu rəqəmə çeviririk (error olmaması üçün)
                    max_val = pd.to_numeric(orders_df['id']).max()
                    new_id = int(max_val) + 1 if not pd.isna(max_val) else 1
                
                add_row("orders", {
                    "id": new_id,
                    "product_name": p_name,
                    "qty": p_qty,
                    "status": "Axtarışda",
                    "winner": "",
                    "final_price": 0.0,
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
                })
                st.toast("Sifariş əlavə olundu!")
                time.sleep(1)
                st.rerun()

# ==========================================
# ƏSAS EKRAN
# ==========================================
if st.session_state['logged_in']:
    user = st.session_state['current_user']
    c1, c2 = st.columns([8, 2])
    c1.title(f"👤 {user} - Şəxsi Kabinet")
    if c2.button("🔄 Yenilə"):
        st.rerun()

    tab1, tab2 = st.tabs(["🔥 Aktiv Bazar", "📜 Tarixçə"])

    with tab1:
        # Yalnız 'Axtarışda' olanları gətir
        orders_df = get_data("orders")
        # Boş ola bilər deyə yoxlayırıq
        if not orders_df.empty and 'status' in orders_df.columns:
            active_orders = orders_df[orders_df['status'] == 'Axtarışda']
        else:
            active_orders = pd.DataFrame()

        if active_orders.empty:
            st.info("Aktiv sifariş yoxdur.")
        else:
            # Sort edək (ən yeni yuxarıda)
            active_orders = active_orders.sort_values(by="id", ascending=False)
            
            for index, row in active_orders.iterrows():
                oid = row['id']
                prod = row['product_name']
                qty = row['qty']
                time_cr = row['created_at']
                
                with st.container(border=True):
                    col_l, col_m, col_r = st.columns([2, 2, 3])
                    
                    with col_l:
                        st.markdown(f"### 📦 {prod}")
                        st.write(f"**Say:** {qty}")
                        st.caption(f"Tarix: {time_cr}")
                    
                    with col_m:
                        st.write("💰 **Təklifiniz:**")
                        # Mənim köhnə qiymətimi tapaq
                        bids_df = get_data("bids")
                        my_val = 0.0
                        
                        if not bids_df.empty:
                            # Filter: order_id və user
                            my_bid = bids_df[(bids_df['order_id'] == oid) & (bids_df['user'] == user)]
                            if not my_bid.empty:
                                # Sonuncu təklifi götürürük
                                my_val = my_bid.iloc[-1]['price']
                        
                        new_price = st.number_input("AZN", value=float(my_val), step=5.0, key=f"inp_{oid}")
                        if st.button("Göndər", key=f"btn_{oid}"):
                            # Bids cədvəlinə əlavə edirik (ID məntiqi ilə)
                            new_bid_id = 1
                            if not bids_df.empty:
                                mx = pd.to_numeric(bids_df['id']).max()
                                new_bid_id = int(mx) + 1 if not pd.isna(mx) else 1
                            
                            add_row("bids", {
                                "id": new_bid_id,
                                "order_id": oid,
                                "user": user,
                                "price": new_price,
                                "timestamp": datetime.now().strftime("%H:%M:%S")
                            })
                            st.toast("Qiymət bazaya yazıldı!")
                            st.rerun()
                    
                    with col_r:
                        st.write("📊 **Liderlər:**")
                        if not bids_df.empty:
                            # Bu sifarişə aid bütün təkliflər
                            relevant_bids = bids_df[bids_df['order_id'] == oid]
                            if not relevant_bids.empty:
                                # Hər istifadəçinin ən son təklifini tapmaq lazımdır (group by)
                                # Lakin sadəlik üçün ən ucuz qiyməti sadə sortla tapırıq
                                sorted_bids = relevant_bids.sort_values(by="price", ascending=True)
                                best_bid = sorted_bids.iloc[0]
                                best_user = best_bid['user']
                                best_p = best_bid['price']
                                
                                st.dataframe(sorted_bids[['user', 'price', 'timestamp']], hide_index=True)
                                
                                if user == best_user:
                                    st.success("🏆 Siz Lidersiniz!")
                                    if st.button("✅ MALI AL (Bitir)", key=f"win_{oid}"):
                                        update_order_status(oid, user, best_p)
                                        st.balloons()
                                        time.sleep(1)
                                        st.rerun()
                                else:
                                    st.warning(f"Lider: {best_user} ({best_p} AZN)")
                            else:
                                st.caption("Təklif yoxdur.")
                        else:
                            st.caption("Təklif yoxdur.")

    with tab2:
        st.subheader("Qazanılmış Tenderlər")
        odf = get_data("orders")
        if not odf.empty:
            my_wins = odf[(odf['winner'] == user) & (odf['status'] == 'Tamamlandı')]
            if not my_wins.empty:
                st.table(my_wins[['product_name', 'qty', 'final_price', 'created_at']])
            else:
                st.write("Hələ ki, qələbə yoxdur.")
else:
    st.info("Zəhmət olmasa giriş edin.")