import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import sqlite3
import datetime
from captcha.image import ImageCaptcha
import random
import string
import io
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Funciones de configuración
def load_config():
    with open('config.yaml') as file:
        config = yaml.load(file, Loader=SafeLoader)
    return config

def save_config(config):
    with open('config.yaml', 'w') as file:
        yaml.dump(config, file, default_flow_style=False)

# Conexión a la base de datos
conn = sqlite3.connect('cac_ltv_data.db')
c = conn.cursor()

# Crear tabla si no existe
c.execute('''CREATE TABLE IF NOT EXISTS calculations
             (id INTEGER PRIMARY KEY, 
              username TEXT,
              date TEXT,
              scenario TEXT,
              ltv REAL,
              cac REAL,
              notes TEXT,
              analysis_date TEXT)''')

# Funciones auxiliares
def format_clp(value):
    return f"{value:,.0f}".replace(",", ".")

def parse_clp(value):
    return int(value.replace(".", ""))

def generate_captcha():
    captcha_text = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    image = ImageCaptcha(width=280, height=90)
    captcha_image = image.generate(captcha_text)
    return captcha_text, captcha_image

def save_calculation(username, scenario, ltv, cac, notes, analysis_date):
    c.execute("INSERT INTO calculations (username, date, scenario, ltv, cac, notes, analysis_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (username, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), scenario, ltv, cac, notes, analysis_date.replace(day=1).strftime("%Y-%m-%d")))
    conn.commit()
    
def get_user_calculations(username):
    c.execute("SELECT * FROM calculations WHERE username = ? ORDER BY analysis_date DESC", (username,))
    return c.fetchall()

# Inicialización del autenticador
config = load_config()
authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days'],
    config['preauthorized']
)
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

# Funciones de interfaz de usuario
def number_input_clp(label, min_value, value, step, help_text):
    return st.text_input(
        label,
        value=format_clp(value),
        help=help_text
    )

def intro():
    st.title("Calculadora de CAC y LTV para Diferentes Modelos de Negocio")
    
    st.markdown("""
    Bienvenido a la calculadora de Customer Acquisition Cost (CAC) y Lifetime Value (LTV) multi-escenario. 
    Esta herramienta te ayudará a entender la rentabilidad de tu modelo de negocio según su tipo específico.

    ### Escenarios disponibles:
    1. **SaaS (Software as a Service)**
    2. **E-commerce**
    3. **Servicios B2B**
    4. **Cooperativa**

    Cada escenario tiene sus propias variables y consideraciones específicas para el cálculo de CAC y LTV.

    ### ¿Por qué son importantes el CAC y el LTV?
    El ratio LTV/CAC te dice si estás ganando más de lo que gastas en adquirir clientes:
    - **< 1**: Estás perdiendo dinero con cada cliente.
    - **1-3**: Tu modelo es marginalmente rentable, pero hay espacio para mejorar.
    - **> 3**: ¡Felicidades! Tu modelo de negocio es saludable y escalable.

    ### Instrucciones
    1. Selecciona tu tipo de negocio.
    2. Ingresa los datos solicitados en pesos chilenos (CLP).
    3. Revisa los resultados y las conclusiones al final de la página.
    4. Experimenta con diferentes valores para ver cómo afectan tus métricas.

    ¡Empecemos!
    """)

    if st.button("Comenzar el cálculo"):
        st.session_state.calculator_page = "scenario_selection"

def scenario_selection():
    st.title("Selección de Escenario")
    scenario = st.selectbox(
        "Elige tu modelo de negocio",
        ("SaaS", "E-commerce", "Servicios B2B", "Cooperativa")
    )
    if st.button("Continuar"):
        st.session_state.scenario = scenario
        st.session_state.calculator_page = "calculator"
def calculator_saas():
    analysis_date = st.date_input("Fecha de análisis", datetime.date.today(), key="analysis_date")
    monthly_revenue = parse_clp(number_input_clp("Ingreso mensual por cliente (CLP)", 0, 50000, 1000, "El ingreso promedio que genera un cliente en un mes."))
    gross_margin = st.number_input("Margen bruto (%)", min_value=0.0, max_value=100.0, value=70.0, step=0.1) / 100
    churn_rate = st.number_input("Tasa de cancelación mensual (%)", min_value=0.0, max_value=100.0, value=5.0, step=0.1) / 100
    expansion_rate = st.number_input("Tasa de expansión mensual (%)", min_value=0.0, max_value=100.0, value=2.0, step=0.1) / 100
    service_cost = parse_clp(number_input_clp("Costo de servicio por cliente (CLP)", 0, 10000, 1000, "El costo directo de servir a un cliente en un mes."))
    conversion_rate = st.number_input("Tasa de conversión de prueba gratuita a pago (%)", min_value=0.0, max_value=100.0, value=20.0, step=0.1) / 100

    ltv = calculate_ltv_saas(monthly_revenue, gross_margin, churn_rate, expansion_rate, service_cost, conversion_rate)

    total_acquisition_cost = parse_clp(number_input_clp("Costo total de adquisición (CLP)", 0, 45000000, 1000000, "El costo total de marketing y ventas para adquirir nuevos clientes."))
    total_customers = st.number_input("Número total de clientes adquiridos", min_value=1, value=200)

    cac = calculate_cac(total_acquisition_cost, total_customers)

    return analysis_date, ltv, cac

def calculator_ecommerce():
    avg_order_value = parse_clp(number_input_clp("Valor promedio de orden (CLP)", 0, 30000, 1000, "El valor promedio de una orden de compra."))
    purchase_frequency = st.number_input("Frecuencia de compra anual", min_value=0.0, value=4.0, step=0.1)
    customer_lifespan = st.number_input("Vida útil del cliente (años)", min_value=0.0, value=3.0, step=0.1)
    gross_margin = st.number_input("Margen bruto (%)", min_value=0.0, max_value=100.0, value=30.0, step=0.1) / 100
    return_rate = st.number_input("Tasa de devolución (%)", min_value=0.0, max_value=100.0, value=5.0, step=0.1) / 100
    reorder_rate = st.number_input("Tasa de recompra (%)", min_value=0.0, max_value=100.0, value=30.0, step=0.1) / 100

    ltv = calculate_ltv_ecommerce(avg_order_value, purchase_frequency, customer_lifespan, gross_margin, return_rate, reorder_rate)

    total_acquisition_cost = parse_clp(number_input_clp("Costo total de adquisición (CLP)", 0, 15000000, 1000000, "El costo total de marketing y publicidad para adquirir nuevos clientes."))
    total_customers = st.number_input("Número total de clientes adquiridos", min_value=1, value=1000)

    cac = calculate_cac(total_acquisition_cost, total_customers)

    return ltv, cac

def calculator_b2b():
    annual_contract_value = parse_clp(number_input_clp("Valor anual del contrato (CLP)", 0, 10000000, 100000, "El valor promedio anual de un contrato B2B."))
    gross_margin = st.number_input("Margen bruto (%)", min_value=0.0, max_value=100.0, value=50.0, step=0.1) / 100
    avg_contract_length = st.number_input("Duración promedio del contrato (años)", min_value=0.0, value=2.0, step=0.1)
    upsell_rate = st.number_input("Tasa de upsell anual (%)", min_value=0.0, max_value=100.0, value=10.0, step=0.1) / 100
    retention_rate = st.number_input("Tasa de retención anual (%)", min_value=0.0, max_value=100.0, value=80.0, step=0.1) / 100

    ltv = calculate_ltv_b2b(annual_contract_value, gross_margin, avg_contract_length, upsell_rate, retention_rate)

    total_acquisition_cost = parse_clp(number_input_clp("Costo total de adquisición (CLP)", 0, 50000000, 1000000, "El costo total de ventas y marketing para adquirir nuevos clientes B2B."))
    total_customers = st.number_input("Número total de clientes adquiridos", min_value=1, value=50)

    cac = calculate_cac(total_acquisition_cost, total_customers)

    return ltv, cac

def calculator_cooperative():
    annual_membership_fee = parse_clp(number_input_clp("Cuota anual de membresía (CLP)", 0, 100000, 10000, "La cuota anual que paga cada miembro de la cooperativa."))
    avg_annual_services = parse_clp(number_input_clp("Promedio de servicios anuales por miembro (CLP)", 0, 500000, 50000, "El valor promedio de servicios utilizados por cada miembro anualmente."))
    gross_margin = st.number_input("Margen bruto (%)", min_value=0.0, max_value=100.0, value=40.0, step=0.1) / 100
    avg_membership_duration = st.number_input("Duración promedio de la membresía (años)", min_value=0.0, value=5.0, step=0.1)
    service_utilization_rate = st.number_input("Tasa de utilización de servicios (%)", min_value=0.0, max_value=100.0, value=70.0, step=0.1) / 100

    ltv = calculate_ltv_cooperative(annual_membership_fee, avg_annual_services, gross_margin, avg_membership_duration, service_utilization_rate)

    total_acquisition_cost = parse_clp(number_input_clp("Costo total de adquisición (CLP)", 0, 10000000, 500000, "El costo total de marketing y promoción para adquirir nuevos miembros."))
    total_members = st.number_input("Número total de nuevos miembros", min_value=1, value=100)

    cac = calculate_cac(total_acquisition_cost, total_members)

    return ltv, cac

def get_recommendations(ratio, scenario, payback_period):
    general_rec = ""
    specific_rec = ""
    benchmark = ""
    payback_rec = ""

    if ratio < 1:
        general_rec = "El modelo de negocio no es sostenible en su estado actual."
    elif 1 <= ratio < 3:
        general_rec = "El modelo es marginalmente rentable, pero hay espacio para mejorar."
    else:
        general_rec = "Tu modelo de negocio es saludable y rentable."

    # Aquí puedes agregar recomendaciones específicas para cada escenario

    benchmark = f"Benchmark típico para {scenario}: LTV/CAC > 3:1"

    if payback_period > 12:
        payback_rec = "Considera estrategias para reducir el período de recuperación a menos de 12 meses."
    elif payback_period < 6:
        payback_rec = "Excelente período de recuperación. Considera si puedes invertir más agresivamente en crecimiento."
    else:
        payback_rec = "Buen período de recuperación. Continúa optimizando para mejorarlo aún más."

    return general_rec, specific_rec, benchmark, payback_rec

def create_bar_chart(chart_df):
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Colores pastel para las barras y la línea
    bar_colors = ['#C5CAE9', '#FFCCBC']  # Azul pastel para CAC, Naranja pastel para LTV
    line_color = '#B39DDB'  # Violeta pastel para la línea de ratio

    fig.add_trace(
        go.Bar(x=chart_df['month'], y=chart_df['cac'], name="CAC", marker_color=bar_colors[0]),
        secondary_y=False,
    )
    
    fig.add_trace(
        go.Bar(x=chart_df['month'], y=chart_df['ltv'], name="LTV", marker_color=bar_colors[1]),
        secondary_y=False,
    )
    
    fig.add_trace(
        go.Scatter(x=chart_df['month'], y=chart_df['ratio'], name="LTV/CAC Ratio", mode='lines+markers', line=dict(color=line_color)),
        secondary_y=True,
    )
    
    fig.update_layout(
        title_text="CAC, LTV, y Ratio en los últimos 6 meses",
        barmode='group',
        plot_bgcolor='white',
        paper_bgcolor='white',
        font={'color': '#4A4A4A'},
    )
    
    fig.update_xaxes(title_text="Mes", showgrid=False)
    fig.update_yaxes(title_text="CLP", secondary_y=False, showgrid=True, gridcolor='#E0E0E0')
    fig.update_yaxes(title_text="Ratio", secondary_y=True, showgrid=False)

    return fig
    
def create_semicircular_gauge(ratio):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = ratio,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "LTV to CAC Ratio", 'font': {'size': 24}},
        gauge = {
            'axis': {'range': [None, 10], 'tickwidth': 1, 'tickcolor': "darkblue"},
            'bar': {'color': "darkblue"},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [0, 1], 'color': 'red'},
                {'range': [1, 3], 'color': 'yellow'},
                {'range': [3, 10], 'color': 'green'}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 3
            }
        }
    ))
    fig.update_layout(font = {'color': "darkblue", 'family': "Arial"})
    return fig

def create_horizontal_bar_gauge(ratio):
    fig = go.Figure(go.Indicator(
        mode = "number+gauge+delta",
        value = ratio,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "LTV to CAC Ratio", 'font': {'size': 24}},
        delta = {'reference': 3, 'position': "top"},
        gauge = {
            'shape': "bullet",
            'axis': {'range': [None, 10]},
            'threshold': {
                'line': {'color': "red", 'width': 2},
                'thickness': 0.75,
                'value': 3
            },
            'steps': [
                {'range': [0, 1], 'color': "lightgray"},
                {'range': [1, 3], 'color': "gray"},
                {'range': [3, 10], 'color': "darkgray"}
            ],
            'bar': {'color': "darkblue"}
        }
    ))
    fig.update_layout(height=200)
    return fig

def create_minimalist_speedometer(ratio):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = ratio,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "LTV to CAC Ratio", 'font': {'size': 24}},
        gauge = {
            'axis': {'range': [None, 10], 'tickwidth': 1, 'tickcolor': "darkblue"},
            'bar': {'color': "darkblue"},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [0, 3], 'color': 'lightgray'},
                {'range': [3, 10], 'color': 'gray'}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 3
            }
        }
    ))
    fig.update_layout(
        font = {'color': "darkblue", 'family': "Arial"},
        annotations=[
            dict(text="0", x=0.1, y=0.4, showarrow=False, font_size=14),
            dict(text="3", x=0.5, y=0.25, showarrow=False, font_size=14),
            dict(text="10", x=0.9, y=0.4, showarrow=False, font_size=14)
        ]
    )
    return fig
    
def display_results(analysis_date, ltv, cac, scenario):
    st.header("Resultados")
    st.write(f"Fecha de análisis: {analysis_date.strftime('%d/%m/%Y')}")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("LTV", f"CLP {format_clp(ltv)}")
    col2.metric("CAC", f"CLP {format_clp(cac)}")
    
    ratio = ltv / cac
    col3.metric("LTV to CAC Ratio", f"{ratio:.2f}")
    
    # Opción para seleccionar el tipo de gráfico
    chart_type = st.selectbox(
        "Selecciona el tipo de gráfico",
        ["Semicircular", "Barra Horizontal", "Velocímetro Minimalista"]
    )
    
    if chart_type == "Semicircular":
        fig = create_semicircular_gauge(ratio)
    elif chart_type == "Barra Horizontal":
        fig = create_horizontal_bar_gauge(ratio)
    else:
        fig = create_minimalist_speedometer(ratio)
    
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Conclusiones y Recomendaciones")
    
    general_rec, specific_rec, benchmark, payback_rec = get_recommendations(ratio, scenario, cac / (ltv / 12))
    
    if ratio < 1:
        st.error(general_rec)
    elif 1 <= ratio < 3:
        st.warning(general_rec)
    else:
        st.success(general_rec)
    
    with st.expander("Ver detalles"):
        st.write(specific_rec)
        st.info(benchmark)
        st.write(payback_rec)
        st.write(f"Período de recuperación: {(cac / (ltv / 12)):.1f} meses")

    notes = st.text_area("Notas sobre este cálculo:", "")
    
    if st.button("Guardar cálculo"):
        save_calculation(st.session_state["username"], scenario, ltv, cac, notes, analysis_date)
        st.success("Cálculo guardado exitosamente!")

    st.header("Historial de cálculos")
    
    calculations = get_user_calculations(st.session_state["username"])
    
    if calculations:
        df = pd.DataFrame(calculations, columns=['id', 'username', 'date', 'scenario', 'ltv', 'cac', 'notes', 'analysis_date'])
        df['analysis_date'] = pd.to_datetime(df['analysis_date'])
        df['month'] = df['analysis_date'].dt.to_period('M')
        
        # Mantener solo el último cálculo para cada mes
        df = df.sort_values('date').groupby('month').last().reset_index()
        
        df['ratio'] = df['ltv'] / df['cac']
        
        six_months_ago = pd.Timestamp.now().to_period('M') - 5  # 6 meses incluyendo el actual
        df_last_6_months = df[df['month'] >= six_months_ago]
        
        months = pd.period_range(end=pd.Timestamp.now().to_period('M'), periods=6, freq='M')
        chart_data = []
        
        for month in months:
            month_data = df_last_6_months[df_last_6_months['month'] == month]
            if not month_data.empty:
                chart_data.append({
                    'month': month.strftime('%B %Y'),
                    'cac': month_data['cac'].iloc[0],
                    'ltv': month_data['ltv'].iloc[0],
                    'ratio': month_data['ratio'].iloc[0]
                })
            else:
                chart_data.append({
                    'month': month.strftime('%B %Y'),
                    'cac': None,
                    'ltv': None,
                    'ratio': None
                })
        
        chart_df = pd.DataFrame(chart_data)
        fig = create_bar_chart(chart_df)
        st.plotly_chart(fig, use_container_width=True)

        # Asegúrate de que cualquier uso posterior de chart_df esté dentro de este bloque if
        # Por ejemplo, si quieres mostrar los datos en una tabla:
        # st.write("Datos del gráfico:", chart_df)
        
    else:
        st.info("No hay cálculos guardados aún.")

def create_user_page():
    st.title("Crear nuevo usuario")
    
    new_username = st.text_input("Nombre de usuario")
    new_name = st.text_input("Nombre completo")
    new_email = st.text_input("Email")
    new_password = st.text_input("Contraseña", type="password")
    confirm_password = st.text_input("Confirmar contraseña", type="password")

    if 'captcha_text' not in st.session_state:
        st.session_state.captcha_text, captcha_image = generate_captcha()
    else:
        captcha_image = ImageCaptcha(width=280, height=90).generate(st.session_state.captcha_text)
    
    st.image(captcha_image, caption='CAPTCHA')
    captcha_input = st.text_input("Ingresa el texto del CAPTCHA")

    if st.button("Crear usuario"):
        if new_password != confirm_password:
            st.error("Las contraseñas no coinciden")
        elif captcha_input.upper() != st.session_state.captcha_text:
            st.error("CAPTCHA incorrecto")
            st.session_state.captcha_text, _ = generate_captcha()
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
                del st.session_state.captcha_text

def calculator():
    st.title(f"Calculadora de CAC y LTV para {st.session_state.scenario}")

    if st.session_state.scenario == "SaaS":
        analysis_date, ltv, cac = calculator_saas()
    elif st.session_state.scenario == "E-commerce":
        analysis_date, ltv, cac = calculator_ecommerce()
    elif st.session_state.scenario == "Servicios B2B":
        analysis_date, ltv, cac = calculator_b2b()
    elif st.session_state.scenario == "Cooperativa":
        analysis_date, ltv, cac = calculator_cooperative()

    display_results(analysis_date, ltv, cac, st.session_state.scenario)

    if st.button("Cambiar escenario"):
        st.session_state.calculator_page = "scenario_selection"

def main():
    if 'page' not in st.session_state:
        st.session_state.page = "login"

    if st.session_state.page == "create_user":
        create_user_page()
    elif st.session_state.page == "login":
        authenticator.login('Login', 'main')
        
        if st.session_state["authentication_status"]:
            authenticator.logout('Logout', 'main')
            st.write(f'Bienvenido *{st.session_state["name"]}*')
            
            if "calculator_page" not in st.session_state:
                st.session_state.calculator_page = "intro"

            if st.session_state.calculator_page == "intro":
                intro()
            elif st.session_state.calculator_page == "scenario_selection":
                scenario_selection()
            elif st.session_state.calculator_page == "calculator":
                calculator()
        elif st.session_state["authentication_status"] == False:
            st.error('Username/password is incorrect')
        elif st.session_state["authentication_status"] == None:
            st.warning('Please enter your username and password')
        
        if st.button("Crear nuevo usuario"):
            st.session_state.page = "create_user"

if __name__ == "__main__":
    main()