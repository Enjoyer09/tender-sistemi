import streamlit as st
import pandas as pd
import time
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- SƏHİFƏ TƏNZİMLƏMƏLƏRİ ---
st.set_page_config(page_title="Global Tender Sistemi", layout="wide")

# --- GOOGLE SHEETS BAZA SİSTEMİ ---
# Bazaya qoşulmaq
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data(worksheet):
    """Məlumatları cədvəldən oxuyur (Cache-siz)"""
    try:
        return conn.read(worksheet=worksheet, ttl=0)
    except:
        return pd.DataFrame() # Boşdursa xəta verməsin

def add_row(worksheet, new_data_dict):
    """Yeni sətir əlavə edir"""
    df = get_data(worksheet)
    new_df = pd.DataFrame([new_data_dict])
    # Pandas concat ilə birləşdiririk
    updated_df = pd.concat([df, new_df], ignore_index=True)
    conn.update(worksheet=worksheet, data=updated_df)

def update_order_status(order_id, winner, price):
    """Sifarişi tamamlayır"""
    df = get_data("orders")
    # ID-yə görə sətri tapıb dəyişirik
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
        # İstifadəçi yoxdursa
        pass 

# --- SESSİYA ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'current_user' not in st.session_state:
    st.session_state['current_user'] = None

# ==========================================
# YAN MENYU (SIDEBAR)
# ==========================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=80)
    st.title("🔐 Giriş Paneli")

    # --- ADMIN PANELI (Şifrə Bərpası - Düzəliş Edildi) ---
    with st.expander("🆘 Admin (Şifrə Sıfırla)"):
        # key="master_input" əlavə etdik ki, qarışmasın
        master_key_input = st.text_input("Master Key", type="password", key="master_input")
        
        # .strip() funksiyası boşluqları silir (admin123 ) -> (admin123)
        if master_key_input.strip() == "admin123":
            st.success("Admin Girişi ✅")
            reset_user = st.selectbox("İşçi seçin", ["Anar", "Samir", "Vüsal", "Orxan", "Elnur"], key="res_user_sel")
            new_pass_admin = st.text_input("Yeni şifrə", key="rst_pass")
            
            if st.button("Şifrəni Dəyiş"):
                users_df = get_data("users")
                # İstifadəçi varmı?
                if not users_df.empty and reset_user in users_df['username'].values:
                    update_user_password(reset_user, new_pass_admin)
                    st.success(f"{reset_user} üçün şifrə yeniləndi!")
                else:
                    # Yoxdursa yaradırıq
                    add_row("users", {"username": reset_user, "password": new_pass_admin})
                    st.success(f"Yeni istifadəçi ({reset_user}) yaradıldı!")
        elif master_key_input:
            st.error("Yanlış Şifrə!")

    st.divider()

    # --- İSTİFADƏÇİ GİRİŞİ ---
    if not st.session_state['logged_in']:
        users_list = ["Seçin...", "Admin", "Anar", "Samir", "Vüsal", "Orxan", "Elnur"]
        selected_user = st.selectbox("İşçi Adı", users_list)

        if selected_user != "Seçin...":
            users_df = get_data("users")
            
            # Bazada bu ad varmı?
            user_exist = False
            if not users_df.empty:
                if selected_user in users_df['username'].values:
                    user_exist = True
            
            if not user_exist:
                st.warning(f"👋 {selected_user}, ilk girişinizdir.")
                new_pass = st.text_input("Yeni Şifrə Təyin Et", type="password")
                if st.button("Qeydiyyatdan Keç"):
                    if new_pass:
                        add_row("users", {"username": selected_user, "password": new_pass})
                        st.success("Qeydiyyat bitdi! İndi daxil olun.")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Şifrə yazın!")
            else:
                # Şifrə yoxlanışı
                password = st.text_input("Şifrənizi yazın", type="password")
                if st.button("Daxil Ol 🚀"):
                    # İstifadəçinin şifrəsini tapırıq
                    user_record = users_df[users_df['username'] == selected_user].iloc[0]
                    real_pass = user_record['password']
                    
                    # String kimi müqayisə edirik (Exceldə rəqəm/yazı qarışmasın deyə)
                    if str(real_pass).strip() == str(password).strip():
                        st.session_state['logged_in'] = True
                        st.session_state['current_user'] = selected_user
                        st.success("Giriş uğurludur!")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("Şifrə yanlışdır!")
    else:
        # GİRİŞ EDİLMİŞ REJİM
        st.success(f"Xoş gəldin, **{st.session_state['current_user']}**")
        
        # Yeni Sifariş Yarat (Yalnız giriş edənlər üçün)
        with st.expander("➕ Yeni Sifariş Yarat"):
            with st.form("add_order_form"):
                p_name = st.text_input("Malın Adı")
                p_qty = st.number_input("Say", 1, 100)
                if st.form_submit_button("Sistemə Vur"):
                    orders_df = get_data("orders")
                    # Yeni ID hesablamaq
                    new_id = 1
                    if not orders_df.empty and 'id' in orders_df.columns:
                        # Boş sətirləri təmizləyib max tapırıq
                        clean_ids = pd.to_numeric(orders_df['id'], errors='coerce').fillna(0)
                        new_id = int(clean_ids.max()) + 1
                    
                    add_row("orders", {
                        "id": new_id,
                        "product_name": p_name,
                        "qty": p_qty,
                        "status": "Axtarışda",
                        "winner": "",
                        "final_price": 0.0,
                        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
                    })
                    st.toast("Sifariş bazara əlavə olundu!")
                    time.sleep(1)
                    st.rerun()

        st.divider()
        if st.button("Çıxış Et 🔒", type="primary"):
            st.session_state['logged_in'] = False
            st.session_state['current_user'] = None
            st.rerun()

# ==========================================
# ƏSAS EKRAN (MAIN AREA)
# ==========================================

if st.session_state['logged_in']:
    user = st.session_state['current_user']
    c1, c2 = st.columns([8, 2])
    c1.title(f"👤 {user} - Şəxsi Kabinet")
    if c2.button("🔄 Yenilə"):
        st.rerun()

    tab1, tab2 = st.tabs(["🔥 Aktiv Bazar", "📜 Tarixçə"])

    # --- TAB 1: AKTİV BAZAR ---
    with tab1:
        orders_df = get_data("orders")
        
        # Sütun yoxdursa və ya boşdursa xəta verməsin
        if orders_df.empty or 'status' not in orders_df.columns:
            st.info("Bazada hələ heç bir məlumat yoxdur.")
            active_orders = pd.DataFrame()
        else:
            active_orders = orders_df[orders_df['status'] == 'Axtarışda']

        if active_orders.empty:
            st.info("Hazırda aktiv sifariş yoxdur.")
        else:
            # Ən yeniləri yuxarıda göstər
            active_orders = active_orders.sort_values(by="id", ascending=False)
            
            for index, row in active_orders.iterrows():
                oid = row['id']
                prod = row['product_name']
                qty = row['qty']
                time_cr = row['created_at']
                
                with st.container(border=True):
                    col_l, col_m, col_r = st.columns([2, 2, 3])
                    
                    # Sol: Məlumat
                    with col_l:
                        st.markdown(f"### 📦 {prod}")
                        st.write(f"**Tələb:** {qty} ədəd")
                        st.caption(f"Yaradılıb: {time_cr}")
                    
                    # Orta: Qiymət Yazmaq
                    with col_m:
                        st.write("💰 **Təklifiniz:**")
                        bids_df = get_data("bids")
                        
                        my_val = 0.0
                        if not bids_df.empty:
                            # Mənim bu mal üçün son qiymətim
                            my_bid = bids_df[(bids_df['order_id'] == oid) & (bids_df['user'] == user)]
                            if not my_bid.empty:
                                my_val = my_bid.iloc[-1]['price']
                        
                        new_price = st.number_input("Qiymət (AZN)", value=float(my_val), step=1.0, key=f"inp_{oid}")
                        
                        if st.button("Göndər", key=f"btn_{oid}"):
                            # ID yaratmaq
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
                            st.toast("Qiymət göndərildi!")
                            time.sleep(1)
                            st.rerun()
                    
                    # Sağ: Liderlər Cədvəli
                    with col_r:
                        st.write("📊 **Canlı Nəticələr:**")
                        if not bids_df.empty:
                            relevant_bids = bids_df[bids_df['order_id'] == oid]
                            if not relevant_bids.empty:
                                # Hər kəsin ən son təklifini tapırıq
                                # (Eyni adam 2 dəfə yazıbsa, sonuncunu götür)
                                latest_bids = relevant_bids.sort_values('id').groupby('user').tail(1)
                                
                                # Qiymətə görə düzürük (Ucuzdan bahaya)
                                sorted_bids = latest_bids.sort_values(by="price", ascending=True)
                                
                                # Lider kimdir?
                                best_bid = sorted_bids.iloc[0]
                                best_user = best_bid['user']
                                best_price = best_bid['price']
                                
                                st.dataframe(sorted_bids[['user', 'price']], hide_index=True)
                                
                                # Qalib Məntiqi
                                if user == best_user:
                                    st.success("🏆 Lider SİZSİNİZ!")
                                    # Yalnız liderdə "AL" düyməsi çıxır
                                    if st.button("✅ MALI AL (Bitir)", key=f"win_{oid}", type="primary"):
                                        update_order_status(oid, user, best_price)
                                        st.balloons()
                                        time.sleep(2)
                                        st.rerun()
                                else:
                                    st.warning(f"⚠️ Lider: **{best_user} ({best_price} AZN)**")
                            else:
                                st.caption("Hələ təklif yoxdur.")
                        else:
                            st.caption("Hələ təklif yoxdur.")

    # --- TAB 2: TARİXÇƏ ---
    with tab2:
        st.subheader("Qazanılmış Tenderlər")
        orders_df = get_data("orders")
        
        if not orders_df.empty and 'status' in orders_df.columns:
            # Yalnız "Tamamlandı" olanlar
            history_df = orders_df[orders_df['status'] == 'Tamamlandı']
            
            # Yalnız mənə aid olanlar (opsional: hamısını görmək istəyirsinizsə filtri yığışdırın)
            # my_wins = history_df[history_df['winner'] == user] <- bu ancaq özünükülərdir
            
            # Gəlin hamısını göstərək ki, kim nə alıb bilinsin
            if not history_df.empty:
                # Sütunları seçirik
                display_df = history_df[['product_name', 'qty', 'winner', 'final_price', 'created_at']]
                st.table(display_df)
            else:
                st.write("Hələ ki, tamamlanmış sifariş yoxdur.")
        else:
            st.write("Baza boşdur.")

else:
    # Giriş edilməyibsə
    st.info("👈 Zəhmət olmasa sol tərəfdən **Adınızı seçib** giriş edin.")
    st.markdown("""
    ### Təlimat:
    1. Sol menyudan adınızı seçin.
    2. Şifrəniz yoxdursa, təyin edib qeydiyyatdan keçin.
    3. Şifrənizi unutmusunuzsa, Adminə müraciət edin.
    """)
