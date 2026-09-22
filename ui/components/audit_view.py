def render_audit_view(events: list[object]) -> None:
    import streamlit as st
    st.subheader("Auditoría")
    if not events:
        st.info("No hay eventos.")
        return
    st.dataframe([
        {"timestamp": str(getattr(event, "timestamp", "")),
         "phase": getattr(getattr(event, "phase", None), "value", ""),
         "actor": getattr(event, "actor", ""), "action": getattr(event, "action_type", ""),
         "hash": getattr(event, "event_hash", "")[:12]}
        for event in events
    ], use_container_width=True)
