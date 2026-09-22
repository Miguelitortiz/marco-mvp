def render_hitl_gate(state_hash: str) -> dict[str, str] | None:
    import streamlit as st
    st.subheader("Puerta de revisión humana")
    with st.form("human_gate"):
        user_id = st.text_input("Usuario")
        decision = st.selectbox("Decisión", ["ACCEPTED", "AMENDED", "REJECTED"])
        submitted = st.form_submit_button("Firmar")
    if submitted and user_id:
        return {"user_id": user_id, "decision": decision, "state_hash": state_hash}
    return None
