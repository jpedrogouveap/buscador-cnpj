import re
import requests
import streamlit as st
from duckduckgo_search import DDGS
import google.generativeai as genai

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Buscador de Mantenedores v2.0",
    page_icon="🏫",
    layout="wide"
)

st.title("🏫 Buscador de Sócios e Mantenedores de Escolas [v2.0]")
st.caption("Investigação OSINT para o setor educacional (BrasilAPI, RDAP/Registro.br, DuckDuckGo e Gemini AI).")

# --- GERENCIAMENTO DA API KEY ---
api_key_salva = st.secrets.get("GEMINI_API_KEY", "")

st.sidebar.header("⚙️ Configurações")
if api_key_salva:
    st.sidebar.success("✅ API Key carregada automaticamente dos Secrets!")
    gemini_api_key = api_key_salva
else:
    gemini_api_key = st.sidebar.text_input(
        "Cole sua API Key do Gemini:",
        type="password",
        help="Insira a chave do Google AI Studio."
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
        dom_limpo = dominio.replace("http://", "").replace("https://", "").replace("www.", "").split("/")[0].strip()
        res = requests.get(f"https://rdap.registro.br/domain/{dom_limpo}", timeout=8)
        if res.status_code == 200:
            data = res.json()
            e_mails = [e.get("email") for e in data.get("entities", []) if "email" in e and e.get("email")]
            return {"emails": list(set(e_mails))}
        return None
    except Exception:
        return None

def buscar_osint_escola(nome_socio: str, razao_social: str, nome_fantasia: str):
    textos_resultados = []
    try:
        ddgs = DDGS()
        if nome_socio and nome_socio != "Sócio não identificado":
            q1 = f'"{nome_socio}" "{nome_fantasia}" (diretor OR mantenedor OR proprietario OR dono OR whatsapp OR celular)'
            r1 = list(ddgs.text(q1, max_results=4))
            for r in r1:
                textos_resultados.append(f"- [Sócio/Liderança]: {r.get('title')}: {r.get('body')}")
            
        q2 = f'"{nome_fantasia}" (escola OR colegio) (direção OR mantenedora OR comercial OR matriculas OR whatsapp OR "9")'
        r2 = list(ddgs.text(q2, max_results=4))
        for r in r2:
            textos_resultados.append(f"- [Instituição]: {r.get('title')}: {r.get('body')}")
            
    except Exception:
        textos_resultados.append("Erro ou limite atingido nas buscas abertas da web.")
        
    return "\n".join(textos_resultados) if textos_resultados else "Nenhum resultado obtido na busca web."

def analisar_com_gemini_escola(api_key: str, nome_socio: str, razao_social: str, nome_fantasia: str, texto_busca: str):
    try:
        genai.configure(api_key=api_key)
        
        # Chamada direta ao modelo indicado na mensagem de erro da API
        model = genai.GenerativeModel('gemini-3.8-flash')

        prompt = f"""
        Você é um analista especialista em prospecção B2B e OSINT para o setor EDUCACIONAL (Escolas e Colégios).
        Analise as informações obtidas na web para a escola '{nome_fantasia}' ({razao_social}) e o sócio/mantenedor '{nome_socio}'.
        
        Texto das buscas:
        {texto_busca}
        
        Instruções de Resposta:
        1. Extraia e liste todos os telefones, celulares, números de WhatsApp e e-mails encontrados.
        2. Classifique a origem de cada contato (ex: Celular/WhatsApp Direto do Mantenedor, Linha da Direção, Secretaria/Matrículas).
        3. Se não houver nenhum número direto localizado, responda exatamente: 'Nenhum número direto localizado nas fontes abertas.'
        4. Seja extremamente objetivo e utilize tópicos (bullet points).
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Erro na análise da IA: {str(e)}"

# --- INTERFACE PRINCIPAL ---
cnpj_input = st.text_input("Digite o CNPJ da escola:", placeholder="Ex: 00.000.000/0001-00")

if st.button("Buscar Contatos", type="primary"):
    if not gemini_api_key:
        st.error("⚠️ Insira ou configure a sua API Key do Gemini antes de realizar a pesquisa.")
    elif not cnpj_input:
        st.warning("⚠️ Digite um CNPJ válido.")
    else:
        cnpj_limpo = limpar_cnpj(cnpj_input)
        if len(cnpj_limpo) != 14:
            st.error("❌ O CNPJ deve conter exatamente 14 dígitos.")
        else:
            with st.spinner("Consultando dados cadastrais na Receita Federal..."):
                dados_empresa = consultar_brasilapi(cnpj_limpo)
            
            if not dados_empresa:
                st.error("❌ CNPJ não encontrado ou indisponível na Receita Federal.")
            else:
                razao_social = dados_empresa.get("razao_social", "N/A")
                nome_fantasia = dados_empresa.get("nome_fantasia") or razao_social
                tel_oficial = f"({dados_empresa.get('ddd_telefone_1', '')[:2]}) {dados_empresa.get('ddd_telefone_1', '')[2:]}"
                socios = dados_empresa.get("qsa", [])
                
                st.success("✅ Escola localizada com sucesso!")
                
                with st.container(border=True):
                    st.subheader("📋 Dados Cadastrais da Instituição")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**Razão Social:**\n{razao_social}")
                        st.markdown(f"**Nome Fantasia / Escola:**\n{nome_fantasia}")
                    with col2:
                        st.markdown(f"**Telefone Oficial (Receita):**\n{tel_oficial if len(tel_oficial) > 4 else 'Não informado'}")
                        st.markdown(f"**CNPJ:**\n{cnpj_limpo}")
                
                site_contato = dados_empresa.get("email")
                if site_contato and isinstance(site_contato, str) and "@" in site_contato:
                    dominio = site_contato.split("@")[-1]
                    dados_rdap = consultar_rdap(dominio)
                    if dados_rdap and dados_rdap.get("emails"):
                        st.info(f"🌐 **Domínio da Instituição ({dominio}):** E-mails públicos encontrados: {', '.join(dados_rdap['emails'])}")
                
                st.divider()
                st.subheader(f"👥 Quadro de Sócios e Mantenedores ({len(socios)} localizados)")
                
                if not socios:
                    st.warning("Nenhum sócio listado no registro público desta empresa.")
                
                for idx, socio in enumerate(socios):
                    nome_socio = socio.get("nome_socio_razao_social") or socio.get("nome_socio") or socio.get("nome") or "Sócio não identificado"
                    cargo = socio.get("qualificacao_socio") or "Sócio/Administrador"
                    
                    with st.expander(f"👤 Mantenedor/Sócio {idx+1}: {nome_socio} ({cargo})", expanded=True):
                        with st.spinner(f"Pesquisando fontes abertas para {nome_socio} e {nome_fantasia}..."):
                            texto_osint = buscar_osint_escola(nome_socio, razao_social, nome_fantasia)
                            resultado_gemini = analisar_com_gemini_escola(gemini_api_key, nome_socio, razao_social, nome_fantasia, texto_osint)
                        
                        st.markdown("**Relatório de Contatos e Liderança:**")
                        st.markdown(resultado_gemini)
                        
                        numeros_encontrados = re.findall(r'(?:55)?\s?(?:[1-9]{2})\s?9?[0-9]{4}[-\s]?[0-9]{4}', resultado_gemini)
                        if numeros_encontrados:
                            num_limpo = re.sub(r'\D', '', numeros_encontrados[0])
                            if not num_limpo.startswith('55'):
                                num_limpo = '55' + num_limpo
                            st.link_button(f"💬 Iniciar conversa no WhatsApp ({nome_socio})", f"https://wa.me/{num_limpo}")
