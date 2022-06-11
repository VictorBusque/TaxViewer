import ssl
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
from prometheus_client import Summary
from json import load as jsonl
from os import listdir

@st.cache(allow_output_mutation=True, suppress_st_warning=True)
def apply_table(df: pd.DataFrame, total: float) -> float:
    remaining = total
    retained, marginal_rate = 0, 0
    for _, section in df.iterrows():
        if remaining == 0: 
            marginal_rate = retention_pct
            break
        retention_pct = float(section["% Tramo"].replace(",", "."))
        max_amount = float(str(section["Fin Tramo"]).replace(",", ".")) - float(str(section["Inicio Tramo"]).replace(",", "."))
        section_retained = min(remaining, max_amount)
        retained += section_retained * retention_pct
        remaining -= section_retained
    return retained, marginal_rate

def format_value(val: float):
    return f"{'{:,}'.format(val)} €"

def floatify(val: str) -> float:
    return float(val.replace(".", "").replace(",", "."))

def get_pie_chart(net, gross_no_taxable, ss_cuota, irpf, divisor=1, name="anual"):
    df = pd.DataFrame()
    if gross_no_taxable:
        df["Concepto"] = ["Neto", "Ingresos no computables", "Cuotas SS", "IRPF*"]
    else:
        df["Concepto"] = ["Neto", "Ingresos no computables", "Cuotas SS", "IRPF"]
    df["Valor"] = [round(net/divisor, 2), round(gross_no_taxable/divisor, 2), round(ss_cuota/divisor, 2), round(irpf/divisor, 2)]
    df["Pull"] = [0, 0, 0, 0.2]
    df["Colors"] = ['rgb(0, 153, 51)', 'rgb(255, 153, 0)', 'rgb(0, 102, 204)', 'rgb(153, 0, 0)']
    
    figure = go.Pie(labels=df["Concepto"], 
                            values=df["Valor"], 
                            pull=df["Pull"],
                            textposition='inside',
                            textinfo='percent+label+value',
                            name=name,
                            marker=dict(colors=df["Colors"], line=dict(color='#000000', width=2)),
                            showlegend=False)
    return figure

def project_pie_chart(yearly_net, gross_salary_no_tax, ss_deduction, total_retention, divisor=1, name="anual"):
    specs = [[{'type':'domain'}]]#, {'type':'domain'}]]
    figs = make_subplots(rows=1, cols=1, specs=specs, subplot_titles=['Anual'])#, 'Mensual'])
    fig_anual = get_pie_chart(yearly_net, gross_salary_no_tax, ss_deduction, total_retention, divisor=divisor, name=name)
    
    figs.add_trace(fig_anual, 1, 1)
    
    st.plotly_chart(figs, use_container_width=True) 
    
    if gross_salary_no_tax:
        st.write("*: El porcentaje de IRPF en el gráfico es inferior al de la tabla porque aquí se tienen en cuenta los ingresos no retenibles.")

def compute_rent_deduc(autonomy_id: str) -> float:    
    rent_deduc = 0
    if autonomy_id == "cataluña":
        rent_deducible = st.checkbox("Deducción por alquiler (si aplica)", value=True)
        if rent_deducible:
            monthly_rent_cost = st.number_input("Introduce tu coste de alquiler mensual (lo que pagas tú solamente)", min_value=0, value=500, step=10)
            rent_deduc = min(300, 0.1*monthly_rent_cost*12)
    elif autonomy_id == "comunidad-de-madrid":
        rent_deducible = st.checkbox("Deducción por alquiler", value=True)
        if rent_deducible:
            monthly_rent_cost = st.number_input("Introduce tu coste de alquiler mensual (lo que pagas tú solamente)", min_value=0, value=500, step=10)
            rent_deduc = min(1000, 0.3*monthly_rent_cost*12)
    return rent_deduc   

def compute_ong_deduc() -> float:
    ong_deducible = st.checkbox("Deducción por aportaciones a asociaciones bonificadas", value=False)
    deduc = 0
    if ong_deducible:
        total_ong = st.number_input("Introduce la cantidad aportada durante el año", min_value=0, value=100, step=10)
        deduc = 0.8*min(150, total_ong) + 0.35*max(total_ong-150, 0)
    return deduc


def compute_irpf(gross_salary_tax, gross_salary_no_tax, ss_pct, rent_deduc, ong_deduc, company_cuota_pct=0.314):
    total_gross = gross_salary_tax + gross_salary_no_tax
        
    # Deductions computation
    ss_cuota = round(ss_pct*total_gross, 2)
    expenses_deduction = 2000
    total_deduction = ss_cuota + expenses_deduction
    personal_post_deduction = 5550
    
    computable_amount = gross_salary_tax - total_deduction
    
    state_retention, state_marginal_pct = apply_table(state_table, computable_amount)
    autonomy_retention, autonomy_marginal_pct = apply_table(autonomy_table, computable_amount)

    state_personal_deduc, _ = apply_table(state_table, personal_post_deduction)
    autonomy_personal_deduc, _ = apply_table(autonomy_table, personal_post_deduction)      
    
    state_retention -= state_personal_deduc
    autonomy_retention -= autonomy_personal_deduc
    
    state_retention = round(state_retention, 2)
    autonomy_retention = round(autonomy_retention, 2)
    total_retention = round(state_retention + autonomy_retention - rent_deduc - ong_deduc, 2)
    retention_pct = round(total_retention/gross_salary_tax * 100, 2)

    yearly_net = round(gross_salary_tax - ss_cuota - total_retention, 2)
    monthly_net = round(yearly_net/12, 2)
    
    st.markdown(f"Con tu sueldo, te tocará pagar **{format_value(total_retention)}** de IRPF en la declaración, que equivale a una retención del **{retention_pct}%** (sin contar otras posibles deducciones por hijos, estar a cargo de personas dependientes, etc). Además, pagas **{format_value(ss_cuota)}** en cuotas a la Seguridad Social.")
    st.markdown(f"Tu sueldo mensual neto (12 pagas) queda en **{ format_value(monthly_net) }**.")
    
    
    project_pie_chart(yearly_net, gross_salary_no_tax, ss_cuota, total_retention, divisor=1, name="Distribución Anual")
    
    user_total_state = round( total_retention + ss_cuota, 2)
    company_cuota_total = round(company_cuota_pct * total_gross, 2)
    st.write(f"Además de los {format_value(user_total_state)} que pagas en impuestos y cuotas, tu empresa paga otros **{format_value(company_cuota_total)}** en cuotas por tí, de modo que en total las instituciones públicas obtienen **{format_value(round(company_cuota_total+user_total_state, 2))}** por tu trabajo.")
    
    total_marginal_pct = state_marginal_pct + autonomy_marginal_pct
    total_marginal_ss_pct = total_marginal_pct +  + ss_pct
    st.write(f"Actualmente, el porcentaje marginal de retención que se te aplica es {total_marginal_pct*100}%, que sumado a lo que pagas de Seguridad Social, te da una retención total de {total_marginal_ss_pct*100}%.")

    avg_save_rate = 0.114
    recommended_save_rate = 0.2
    average_saves = round(avg_save_rate*monthly_net)
    recommended_saves = round(recommended_save_rate*monthly_net)
    st.write(f"Si ahorraras como el español medio en 2021 ahorrarías **{format_value(average_saves)}** mensuales ({format_value(average_saves*12)} al año), aunque los expertos te recomendarían ahorrar por lo menos **{format_value(recommended_saves)}** mensuales ({format_value(recommended_saves*12)} al año)")
    
            
    max_price_rent = round((0.25*yearly_net)/12), round((0.35*yearly_net)/12)
    st.write(f"Con este sueldo deberías poderte permitir pagar un alquiler de **{format_value(max_price_rent[0])}** mensuales de forma cómoda, y los expertos recomiendan que no superes los **{format_value(max_price_rent[1])}** mensuales en un alquiler.")
    
    return yearly_net, ss_cuota, total_retention

if __name__ == "__main__":
    title = st.title('Calculadora de IRPF')
    year = st.selectbox("Selecciona el año", options=[2022], index=0)
    autonomies = [autonomy.title()[:-4].replace("-", " ") for autonomy in listdir(f"tables/{year}") if not autonomy == "state.csv"]
    autonomy = st.selectbox("Selecciona la comunidad autónoma", options=autonomies, index=0)
    autonomy_id = autonomy.lower().replace(' ', '-')
    
    # Loading of right tables
    state_table = pd.read_csv(f"tables/{year}/state.csv", sep=";")
    autonomy_table = pd.read_csv(f"tables/{year}/{autonomy_id}.csv", sep=";")
    
    # Input
    # gross_salary_tax = st.slider("Introduce tu sueldo retenible por IRPF", min_value=1000, value=30000, max_value=200000, step=500)
    gross_salary_tax = st.number_input("Introduce tu sueldo retenible por IRPF", min_value=1000, value=30000, max_value=200000, step=500)
    gross_salary_no_tax = st.number_input("Introduce tu sueldo NO retenible por IRPF (p.e. tarjeta restaurante, transporte, guardería, seguro médico, etc)", min_value=0, value=0, step=100)
    
    indef = st.checkbox("Contrato laboral indefinido", value=True)
    if indef: ss_pct = 0.047+0.0155+0.001
    else: ss_pct = 0.047+0.016+0.001
    
    ong_deduc = compute_ong_deduc()
    rent_deduc = 0
    # rent_deduc = compute_rent_deduc(autonomy_id)
    
    # compute = st.button("Calcula")
    compute = True
    if compute:
        yearly_net, yearly_ss, yearly_irpf = compute_irpf(gross_salary_tax, gross_salary_no_tax, ss_pct, rent_deduc, ong_deduc)
        