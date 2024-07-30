import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import sqlite3
import datetime
import os
import random

# Configuración de la base de datos
def init_db():
    if 'STREAMLIT_APP_NAME' in os.environ:  # Estamos en Streamlit Cloud
        db_path = '/mount/data/cac_ltv_data.db'
    else:  # Desarrollo local
        db_path = 'cac_ltv_data.db'

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS calculations
                 (id INTEGER PRIMARY KEY, 
                  username TEXT,
                  date TEXT,
                  scenario TEXT,
                  ltv REAL,
                  cac REAL,
                  notes TEXT)''')
    conn.commit()
    return conn

conn = init_db()

# Funciones de configuración
def load_config():
    if 'STREAMLIT_APP_NAME' in os.environ:  # Estamos en Streamlit Cloud
        return st.secrets['config']
    else:
        with open('config.yaml') as file:
            return yaml.load(file, Loader=SafeLoader)

def save_config(config):
    if 'STREAMLIT_APP_NAME' not in os.environ:  # Solo en desarrollo local
        with open('config.yaml', 'w') as file:
            yaml.dump(config, file, default_flow_style=False)

config = load_config()
authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days'],
    config['preauthorized']
)

# Funciones auxiliares
def format_clp(value):
    return f"{value:,.0f}".replace(",", ".")

def parse_clp(value):
    return int(value.replace(".", ""))

def save_calculation(username, scenario, ltv, cac, notes):
    date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c = conn.cursor()
    c.execute("INSERT INTO calculations (username, date, scenario, ltv, cac, notes) VALUES (?, ?, ?, ?, ?, ?)",
              (username, date, scenario, ltv, cac, notes))
    conn.commit()

def get_user_calculations(username):
    c = conn.cursor()
    c.execute("SELECT * FROM calculations WHERE username = ? ORDER BY date DESC", (username,))
    return c.fetchall()

def generate_simple_challenge():
    a = random.randint(1, 10)
    b = random.randint(1, 10)
    return f"{a} + {b}", str(a + b)

# ... [Continúa en la Parte 2] ...
# Funciones de cálculo
def calculate_cac(total_acquisition_cost, total_customers):
    return total_acquisition_cost / total_customers

def calculate_ltv_saas(monthly_revenue, gross_margin, churn_rate, expansion_rate, service_cost, conversion_rate):
    net_revenue = monthly_revenue - service_cost
    net_margin = gross_margin - (service_cost / monthly_revenue)
    growth_rate = expansion_rate - churn_rate
    if growth_rate <= 0:
        lifetime = 1 / churn_rate
    else:
        lifetime = (1 / churn_rate) * (1 + (growth_rate / churn_rate))
    ltv = (net_revenue * net_margin * lifetime) / conversion_rate
    return ltv

def calculate_ltv_ecommerce(avg_order_value, purchase_frequency, customer_lifespan, gross_margin, return_rate, reorder_rate):
    net_order_value = avg_order_value * (1 - return_rate)
    annual_revenue = net_order_value * purchase_frequency
    lifetime_revenue = annual_revenue * customer_lifespan * (1 + reorder_rate)
    ltv = lifetime_revenue * gross_margin
    return ltv

def calculate_ltv_b2b(annual_contract_value, gross_margin, avg_contract_length, upsell_rate, retention_rate):
    base_ltv = annual_contract_value * gross_margin * avg_contract_length
    upsell_value = base_ltv * upsell_rate * (avg_contract_length - 1)
    retention_value = base_ltv * retention_rate * (avg_contract_length - 1)
    ltv = base_ltv + upsell_value + retention_value
    return ltv

def calculate_ltv_cooperative(annual_membership_fee, avg_annual_services, gross_margin, avg_membership_duration, service_utilization_rate):
    annual_value = annual_membership_fee + (avg_annual_services * service_utilization_rate)
    ltv = annual_value * gross_margin * avg_membership_duration
    return ltv

# Funciones de interfaz de usuario para cálculos
def number_input_clp(label, min_value, value, step, help_text):
    return st.text_input(
        label,
        value=format_clp(value),
        help=help_text
    )

def calculator_saas():
    st.header("Cálculo de LTV para SaaS")
    
    monthly_revenue = number_input_clp(
        "Ingreso mensual por cliente (CLP)", 0, 50000, 1000,
        "El ingreso promedio que genera un cliente en un mes."
    )
    gross_margin = st.number_input("Margen bruto (%)", min_value=0, max_value=100, value=70)
    churn_rate = st.number_input("Tasa de cancelación mensual (%)", min_value=0, max_value=100, value=5)
    expansion_rate = st.number_input("Tasa de expansión mensual (%)", min_value=0, max_value=100, value=2)
    service_cost = number_input_clp("Costo de servicio por cliente (CLP)", 0, 10000, 1000, "Costo mensual de servir a un cliente.")
    conversion_rate = st.number_input("Tasa de conversión de prueba gratuita a pago (%)", min_value=0, max_value=100, value=20)

    ltv = calculate_ltv_saas(parse_clp(monthly_revenue), gross_margin/100, churn_rate/100, expansion_rate/100, parse_clp(service_cost), conversion_rate/100)

    st.header("Cálculo de CAC")
    total_acquisition_cost = number_input_clp("Costo total de adquisición (CLP)", 0, 45000000, 1000000, "Costo total de marketing y ventas.")
    total_customers = st.number_input("Número total de clientes adquiridos", min_value=1, value=200)

    return ltv, calculate_cac(parse_clp(total_acquisition_cost), total_customers)

def calculator_ecommerce():
    st.header("Cálculo de LTV para E-commerce")
    
    avg_order_value = number_input_clp("Valor promedio de orden (CLP)", 0, 30000, 1000, "Valor promedio de una compra.")
    purchase_frequency = st.number_input("Frecuencia de compra anual", min_value=0, value=4)
    customer_lifespan = st.number_input("Vida útil del cliente (años)", min_value=0, value=3)
    gross_margin = st.number_input("Margen bruto (%)", min_value=0, max_value=100, value=30)
    return_rate = st.number_input("Tasa de devolución (%)", min_value=0, max_value=100, value=5)
    reorder_rate = st.number_input("Tasa de recompra (%)", min_value=0, max_value=100, value=30)

    ltv = calculate_ltv_ecommerce(parse_clp(avg_order_value), purchase_frequency, customer_lifespan, gross_margin/100, return_rate/100, reorder_rate/100)

    st.header("Cálculo de CAC")
    total_acquisition_cost = number_input_clp("Costo total de adquisición (CLP)", 0, 15000000, 1000000, "Costo total de marketing y publicidad.")
    total_customers = st.number_input("Número total de clientes adquiridos", min_value=1, value=1000)

    return ltv, calculate_cac(parse_clp(total_acquisition_cost), total_customers)

def calculator_b2b():
    st.header("Cálculo de LTV para Servicios B2B")
    
    annual_contract_value = number_input_clp("Valor anual del contrato (CLP)", 0, 5000000, 1000000, "Valor promedio anual de un contrato B2B.")
    gross_margin = st.number_input("Margen bruto (%)", min_value=0, max_value=100, value=60)
    avg_contract_length = st.number_input("Duración promedio del contrato (años)", min_value=0, value=3)
    upsell_rate = st.number_input("Tasa de upsell anual (%)", min_value=0, max_value=100, value=10)
    retention_rate = st.number_input("Tasa de retención después del contrato inicial (%)", min_value=0, max_value=100, value=70)

    ltv = calculate_ltv_b2b(parse_clp(annual_contract_value), gross_margin/100, avg_contract_length, upsell_rate/100, retention_rate/100)

    st.header("Cálculo de CAC")
    total_acquisition_cost = number_input_clp("Costo total de adquisición (CLP)", 0, 20000000, 1000000, "Costo total de marketing, ventas y proceso de adquisición.")
    total_customers = st.number_input("Número total de clientes adquiridos", min_value=1, value=10)

    return ltv, calculate_cac(parse_clp(total_acquisition_cost), total_customers)

def calculator_cooperative():
    st.header("Cálculo de LTV para Cooperativa")
    
    annual_membership_fee = number_input_clp("Cuota anual de membresía (CLP)", 0, 50000, 1000, "Cuota anual que paga cada miembro.")
    avg_annual_services = number_input_clp("Promedio de servicios anuales utilizados (CLP)", 0, 500000, 10000, "Valor promedio de servicios por miembro al año.")
    retention_rate = st.number_input("Tasa de retención anual (%)", min_value=0, max_value=100, value=90)
    avg_membership_duration = 1 / (1 - retention_rate/100)
    gross_margin = st.number_input("Margen bruto (%)", min_value=0, max_value=100, value=40)
    service_utilization_rate = st.number_input("Tasa de utilización de servicios (%)", min_value=0, max_value=100, value=75)

    ltv = calculate_ltv_cooperative(parse_clp(annual_membership_fee), parse_clp(avg_annual_services), gross_margin/100, avg_membership_duration, service_utilization_rate/100)

    st.header("Cálculo de CAC")
    total_acquisition_cost = number_input_clp("Costo total de adquisición (CLP)", 0, 10000000, 500000, "Costo total de marketing y proceso de incorporación.")
    total_new_members = st.number_input("Número total de nuevos miembros", min_value=1, value=100)

    return ltv, calculate_cac(parse_clp(total_acquisition_cost), total_new_members)

# ... [Continúa en la Parte 3] ...
# Funciones para mostrar resultados y recomendaciones
def get_industry_benchmarks(scenario):
    benchmarks = {
        "SaaS": {
            "LTV/CAC ratio": "3:1 - 5:1",
            "Churn rate": "5% - 7% anual",
            "Gross margin": "80% - 90%"
        },
        "E-commerce": {
            "LTV/CAC ratio": "3:1 - 4:1",
            "Conversion rate": "2% - 3%",
            "Average order value": "Varía según la industria"
        },
        "Servicios B2B": {
            "LTV/CAC ratio": "3:1 - 7:1",
            "Sales cycle": "3 - 6 meses",
            "Customer retention rate": "80% - 90%"
        },
        "Cooperativa": {
            "LTV/CAC ratio": "3:1 - 5:1",
            "Member retention rate": "85% - 95%",
            "Service utilization rate": "60% - 80%"
        }
    }
    return benchmarks.get(scenario, {})

def get_recommendations(ratio, scenario, payback_period):
    general_rec = ""
    specific_rec = ""
    benchmark = ""

    industry_benchmarks = get_industry_benchmarks(scenario)
    
    if ratio < 1:
        general_rec = "El modelo de negocio no es sostenible en su estado actual."
    elif 1 <= ratio < 3:
        general_rec = "El modelo es marginalmente rentable, pero hay espacio para mejorar."
    else:
        general_rec = "Tu modelo de negocio es saludable y rentable."
    
    # Aquí puedes agregar recomendaciones específicas para cada escenario y rango de ratio
    
    benchmark = f"Benchmarks de la industria para {scenario}:\n"
    for key, value in industry_benchmarks.items():
        benchmark += f"- {key}: {value}\n"

    payback_rec = f"Tu período de recuperación es de {payback_period:.1f} meses. "
    if payback_period > 12:
        payback_rec += "Considera estrategias para reducir este período a menos de 12 meses para mejorar el flujo de caja."
    elif payback_period < 6:
        payback_rec += "Este es un excelente período de recuperación. Considera si puedes invertir más agresivamente en crecimiento."
    else:
        payback_rec += "Este es un buen período de recuperación. Continúa optimizando para mejorarlo aún más."

    return general_rec, specific_rec, benchmark, payback_rec

def display_results(ltv, cac, scenario):
    st.header("Resultados")
    st.write(f"LTV: CLP {format_clp(ltv)}")
    st.write(f"CAC: CLP {format_clp(cac)}")

    ratio = ltv / cac
    st.write(f"Ratio LTV/CAC: {ratio:.2f}")

    payback_period = cac / (ltv / 12)  # Asumiendo que LTV está en valor anual

    st.header("Conclusiones y Recomendaciones")
    
    general_rec, specific_rec, benchmark, payback_rec = get_recommendations(ratio, scenario, payback_period)
    
    if ratio < 1:
        st.error(general_rec)
    elif 1 <= ratio < 3:
        st.warning(general_rec)
    else:
        st.success(general_rec)
    
    st.write(specific_rec)
    st.info(benchmark)
    st.write(payback_rec)
    
    st.write(f"Período de recuperación: {payback_period:.1f} meses")

    notes = st.text_area("Notas sobre este cálculo:", "")
    if st.button("Guardar cálculo"):
        save_calculation(st.session_state["username"], scenario, ltv, cac, notes)
        st.success("Cálculo guardado exitosamente!")

    st.header("Historial de cálculos")
    calculations = get_user_calculations(st.session_state["username"])
    for calc in calculations:
        st.write(f"Fecha: {calc[2]}, Escenario: {calc[3]}, LTV: {calc[4]}, CAC: {calc[5]}")
        st.write(f"Notas: {calc[6]}")
        st.write("---")

# Funciones de autenticación y registro
def create_user_page():
    st.title("Crear nuevo usuario")
    
    new_username = st.text_input("Nombre de usuario")
    new_name = st.text_input("Nombre completo")
    new_email = st.text_input("Email")
    new_password = st.text_input("Contraseña", type="password")
    confirm_password = st.text_input("Confirmar contraseña", type="password")

    if 'challenge' not in st.session_state:
        st.session_state.challenge, st.session_state.challenge_answer = generate_simple_challenge()
    
    st.write(f"Por favor, resuelve esta operación simple: {st.session_state.challenge}")
    challenge_input = st.text_input("Tu respuesta")

    if st.button("Crear usuario"):
        if new_password != confirm_password:
            st.error("Las contraseñas no coinciden")
        elif challenge_input != st.session_state.challenge_answer:
            st.error("Respuesta incorrecta")
            st.session_state.challenge, st.session_state.challenge_answer = generate_simple_challenge()
        else:
            config = load_config()
            if new_username in config['credentials']['usernames']:
                st.error("El nombre de usuario ya existe")
            else:
                hashed_password = stauth.Hasher([new_password]).generate()[0]
                config['credentials']['usernames'][new_username] = {
                    'email': new_email,
                    'name': new_name,
                    'password': hashed_password
                }
                save_config(config)
                st.success("Usuario creado exitosamente")
                st.info("Por favor, inicia sesión con tu nuevo usuario")
                st.session_state.page = "login"
                del st.session_state.challenge
                del st.session_state.challenge_answer

# Función principal
def main():
    if 'page' not in st.session_state:
        st.session_state.page = "login"

    if st.session_state.page == "create_user":
        create_user_page()
    elif st.session_state.page == "login":
        # Corrección de la llamada a login()
        name, authentication_status, username = authenticator.login('Login', 'main')
        
        # El resto de tu función main() permanece igual
        if authentication_status:
            authenticator.logout('Logout', 'main')
            st.write(f'Bienvenido *{name}*')
            
            # ... (resto del código)

if __name__ == "__main__":
    try:
        main()
    finally:
        conn.close()
