def render_diff_view(diff: object) -> None:
    import streamlit as st
    st.subheader("Diff")
    st.caption(f"+{getattr(diff, 'additions', 0)} / -{getattr(diff, 'deletions', 0)}")
    st.code(getattr(diff, "unified", ""), language="diff")
