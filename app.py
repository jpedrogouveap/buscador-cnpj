import re
import requests
import streamlit as st
from duckduckgo_search import DDGS
import google.generativeai as genai

# Configuração visual do aplicativo
st.set_page_config(
    page_title="Buscador de Sócios OSINT",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 Buscador Gratuito de Contatos de Sócios")
st.caption("Consulta automatizada via BrasilAPI, RDAP (Registro.br), OSINT Web e Gemini AI.")

# Barra lateral para colar a chave
st.sidebar.header("Configuração")
gemini_api_key = st.sidebar.text_input(
    "Cole sua API Key do Gemini (Pessoal):",
    type="password",
    help="Cole a chave que você gerou no Google AI Studio com seu Gmail Pessoal."
)

def limpar_cnpj(cnpj_raw: str) -> str:
    return re.sub(r'\D', '', cnpj_raw)

def consultar_brasilapi(cnpj: str):
    try:
        res = requests.get(f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}", timeout=10)
        if res.status_code == 200:
            return res.json()
        return None
    except Exception:
        return None

def consultar_rdap(dominio: str):
    try:
        dom_limpo = dominio.replace("http://", "").replace("https://", "").replace("www.", "").split("/")[0]
        res = requests.get(f"https://rdap.registro.br/domain/{dom_limpo}", timeout=8)
        if res.status_code == 200:
            data = res.json()
            e_mails = [e.get("email") for e in data.get("entities", []) if "email" in e]
            return {"emails": list(set(e_mails))}
        return None
    except Exception:
        return None

def buscar_osint_duckduckgo(nome_socio: str, razao_social: str):
    try:
        ddgs = DDGS()
        query = f'"{nome_socio}" "{razao_social}" (telefone OR whatsapp OR celular OR contato)'
        results = list(ddgs.text(query, max_results=5))
        return "\n".join([f"- {r.get('title')}: {r.get('body')}" for r in results])
    except Exception:
        return "Erro ou limite atingido nas buscas abertas da web."

def analisar_com_gemini(api_key: str, nome_socio: str, razao_social: str, texto_busca: str):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        prompt = f"""
        Você é um analista especialista em investigação de contatos (OSINT).
        Analise o texto retornado da internet para o sócio '{nome_socio}' da empresa '{razao_social}'.
        
        Texto das buscas:
        {texto_busca}
        
        Instruções:
        1. Extraia qualquer número de celular, telefone fixo ou link de WhatsApp associado a essa pessoa ou empresa.
        2. Se encontrar números, formate-os e indique o nível de certeza (ex: Alto para celular direto do sócio, Médio para telefone comercial).
        3. Se não houver nenhum número no texto, responda exatamente: 'Nenhum número direto localizado nas fontes abertas.'
        4. Seja extremamente direto. Use tópicos simples.
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Erro na análise da IA: {str(e)}"

# Entrada do CNPJ
cnpj_input = st.text_input("Digite o CNPJ da empresa:", placeholder="Ex: 00.000.000/0001-00")

if st.button("Buscar Contatos", type="primary"):
    if not gemini_api_key:
        st.error("⚠️ Insira sua API Key do Gemini na barra lateral esquerda antes de buscar.")
    elif not cnpj_input:
        st.warning("⚠️ Digite um CNPJ.")
    else:
        cnpj_limpo = limpar_cnpj(cnpj_input)
        if len(cnpj_limpo) != 14:
            st.error("❌ O CNPJ deve conter 14 dígitos.")
        else:
            with st.spinner("Consultando dados da Receita Federal..."):
                dados_empresa = consultar_brasilapi(cnpj_limpo)
            
            if not dados_empresa:
                st.error("❌ CNPJ não encontrado ou indisponível na Receita Federal.")
            else:
                razao_social = dados_empresa.get("razao_social", "N/A")
                nome_fantasia = dados_empresa.get("nome_fantasia") or razao_social
                tel_oficial = f"({dados_empresa.get('ddd_telefone_1', '')[:2]}) {dados_empresa.get('ddd_telefone_1', '')[2:]}"
                socios = dados_empresa.get("qsa", [])
                
                st.success("✅ Empresa localizada!")
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Razão Social", razao_social)
                col2.metric("Nome Fantasia", nome_fantasia)
                col3.metric("Telefone Oficial (Receita)", tel_oficial if len(tel_oficial) > 4 else "Não informado")
                
                # Registro.br Check
                site_contato = dados_empresa.get("email", "")
                if "@" in site_contato:
                    dominio = site_contato.split("@")[-1]
                    dados_rdap = consultar_rdap(dominio)
                    if dados_rdap and dados_rdap.get("emails"):
                        st.info(f"🌐 **Domínio da empresa ({dominio}):** E-mails públicos encontrados: {', '.join(dados_rdap['emails'])}")
                
                st.divider()
                st.subheader(f"👥 Quadro de Sócios ({len(socios)} encontrados)")
                
                if not socios:
                    st.warning("Nenhum sócio listado no cadastro público desta empresa.")
                
                for idx, socio in enumerate(socios):
                    nome_socio = socio.get("nome_socio_razao_social")
                    cargo = socio.get("qualificacao_socio")
                    
                    with st.expander(f"👤 {nome_socio} ({cargo})", expanded=True):
                        with st.spinner(f"Pesquisando rastros públicos na web para {nome_socio}..."):
                            texto_osint = buscar_osint_duckduckgo(nome_socio, razao_social)
                            resultado_gemini = analisar_com_gemini(gemini_api_key, nome_socio, razao_social, texto_osint)
                        
                        st.markdown("**Relatório de Contatos Encontrados:**")
                        st.markdown(resultado_gemini)
                        
                        # Extrai telefone para gerar o botão do WhatsApp
                        numeros_encontrados = re.findall(r'(?:55)?\s?(?:[1-9]{2})\s?9?[0-9]{4}[-\s]?[0-9]{4}', resultado_gemini)
                        if numeros_encontrados:
                            num_limpo = re.sub(r'\D', '', numeros_encontrados[0])
                            if not num_limpo.startswith('55'):
                                num_limpo = '55' + num_limpo
                            st.link_button(f"💬 Iniciar conversa no WhatsApp com {nome_socio}", f"https://wa.me/{num_limpo}")
