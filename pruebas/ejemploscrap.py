import os
import json
import re
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from langgraph.graph import MessagesState, StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage

# Cargar variables de entorno
load_dotenv()

# Estado personalizado
class CustomState(MessagesState):
    trigger: str

# Inicializar LLM
def initialize_llm():
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        raise ValueError("La clave de la API de Google no está definida")
    
    return ChatGoogleGenerativeAI(
        google_api_key=google_api_key,
        model="gemini-1.5-flash",
        temperature=0.7
    )

# Limpiar respuesta del LLM
def clean_llm_response(response_text):
    return re.sub(r'```json\s*|\s*```', '', response_text).strip()

# Extraer contenido del artículo
def extract_article_content(soup):
    # Extraer párrafos
    paragraphs = soup.find_all('p')
    if paragraphs:
        valid_paragraphs = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20]
        if valid_paragraphs:
            return " ".join(valid_paragraphs)
    
    # Extraer del artículo
    article = soup.find('article')
    if article:
        for tag in article.find_all(['script', 'style', 'nav', 'footer', 'header']):
            tag.decompose()
        return article.get_text(separator=' ', strip=True)
    
    # Extraer del div principal
    main_content = soup.find('div', class_=lambda x: x and ('content' in x.lower() or 'article' in x.lower()))
    if main_content:
        for tag in main_content.find_all(['script', 'style', 'nav', 'footer', 'header']):
            tag.decompose()
        return main_content.get_text(separator=' ', strip=True)
    
    return ""

# Scraper de noticias
def news_scraper(state: CustomState) -> CustomState:
    if state["trigger"] != "Y":
        state["messages"].append(HumanMessage(content="Sistema no iniciado. Se requiere trigger 'Y'."))
        return state
    
    try:
        url = "https://oem.com.mx/diariodequeretaro/policiaca/"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        news_items = soup.find_all(['h2', 'h3'], class_=lambda x: x and 'Typography' in x)
        news_data = []
        
        for item in news_items[:3]:
            link = item.find_parent('a', href=True)
            if not link:
                continue
                
            title = item.get_text(strip=True)
            full_url = link['href']
            if not full_url.startswith('http'):
                full_url = "https://oem.com.mx" + full_url
            
            try:
                article_response = requests.get(full_url, headers=headers, timeout=10)
                article_soup = BeautifulSoup(article_response.content, 'html.parser')
                
                date_elem = article_soup.find('span', class_=lambda x: x and 'Typography' in x)
                date_text = date_elem.get_text(strip=True) if date_elem else "Fecha no encontrada"
                
                content = extract_article_content(article_soup)
                
                llm = initialize_llm()
                analyze_prompt = f"""
                Analiza el siguiente contenido de una noticia policiaca y extrae:
                1. El lugar exacto donde ocurrió el incidente (colonia, calle, delegación, etc.)
                2. La fecha del incidente
                3. La hora aproximada del incidente
                4. Un resumen claro del evento
                
                Responde en formato JSON con estos campos: "lugar", "fecha", "hora", "resumen"
                NO incluyas markdown, sólo el JSON.
                
                Contenido de la noticia:
                {content}
                """
                
                response = llm.invoke([HumanMessage(content=analyze_prompt)])
                cleaned_response = clean_llm_response(response.content)
                
                try:
                    details = json.loads(cleaned_response)
                    
                    news_item = {
                        "noticia": title,
                        "url": full_url,
                        "fecha_publicacion": date_text,
                        "lugar": details.get("lugar", "No especificado"),
                        "fecha_incidente": details.get("fecha", "No especificada"),
                        "hora_incidente": details.get("hora", "No especificada"),
                        "resumen": details.get("resumen", "No disponible")
                    }
                    
                    news_data.append(news_item)
                    
                except json.JSONDecodeError:
                    news_item = {
                        "noticia": title,
                        "url": full_url,
                        "fecha_publicacion": date_text,
                        "lugar": "No extraído",
                        "fecha_incidente": "No extraída",
                        "hora_incidente": "No extraída",
                        "resumen": "No disponible"
                    }
                    news_data.append(news_item)
                
            except Exception:
                continue
        
        if not news_data:
            state["messages"].append(HumanMessage(content="[]"))
            return state
        
        state["messages"].append(HumanMessage(content=json.dumps(news_data, indent=2, ensure_ascii=False)))
        
    except Exception as e:
        state["messages"].append(HumanMessage(content=f"Error: {str(e)}"))
    
    return state

# Procesador de la ubicación
def location_agent(state: CustomState) -> CustomState:
    if state["trigger"] != "Y":
        state["messages"].append(AIMessage(content="Sistema no iniciado. Se requiere trigger 'Y'."))
        return state
    
    try:
        last_message = state["messages"][-1].content
        if last_message.startswith("Error") or last_message == "[]":
            state["messages"].append(AIMessage(content=last_message))
            return state
        
        news_data = json.loads(last_message)
        
        # Simplemente devolver los datos tal como están
        state["messages"].append(AIMessage(content=json.dumps(news_data, indent=2, ensure_ascii=False)))
        
    except Exception as e:
        state["messages"].append(AIMessage(content=f"Error: {str(e)}"))
    
    return state

# Construir el grafo
graph_builder = StateGraph(CustomState)
graph_builder.add_node("scraper", news_scraper)
graph_builder.add_node("location_agent", location_agent)
graph_builder.add_edge(START, "scraper")
graph_builder.add_edge("scraper", "location_agent")
graph_builder.add_edge("location_agent", END)
graph = graph_builder.compile()

# La función se llama simplemente cuando se ejecuta el archivo
initial_state = {"messages": [], "trigger": "Y"}
result = graph.invoke(initial_state)
print(result["messages"][-1].content)