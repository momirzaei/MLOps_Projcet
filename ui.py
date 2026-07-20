import streamlit as st
import requests

API_URL = "http://127.0.0.1:8000/ask"

st.set_page_config(page_title="Retail Data Assistant", page_icon="📊")
st.title(" Retail Data Assistant")
st.markdown("Ask me anything about your Medallion Gold Layer data!")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("e.g. What is the total net revenue?"):
    with st.chat_message("user"):
        st.markdown(prompt)
    
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        with st.spinner("Analyzing data..."):
            try:
                response = requests.post(
                    API_URL, 
                    json={"question": prompt},
                    timeout=30
                )
                
                if response.status_code == 200:
                    answer = response.json().get("answer", "No answer found.")
                    st.markdown(answer)
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                else:
                    st.error(f"Error from server: {response.status_code}")
            
            except requests.exceptions.ConnectionError:
                st.error("Cannot connect to the API. Is your Docker container running?")