"""Test Lab: 40-case labelled evaluation runner and diff inspector."""

import sys
from pathlib import Path
_ROOT_DIR = Path(__file__).resolve().parent.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))


import streamlit as st
import pandas as pd
from src.evaluation import load_test_cases, execute_evaluation_case, run_all_evaluations
from src.database import get_db_connection
from src.ui import render_page_header, render_sidebar_info, render_kpi_card, inject_custom_css

st.set_page_config(page_title="Test Lab | Alliance Admissions", layout="wide")
inject_custom_css()
render_sidebar_info()

render_page_header(
    title="Evaluation Test Lab (40-Case Labelled Suite)",
    subtitle="Benchmarking suite across 8 Normal High, 9 Normal Medium, 7 Normal Low, 8 Exceptions, 5 What-Ifs, and 3 Failure Injections.",
    icon="🧪",
    badge="Rigorous Operational Benchmark Suite"
)

test_cases = load_test_cases()

# Fetch past runs
conn = get_db_connection()
runs_df = pd.read_sql_query("SELECT * FROM evaluation_runs ORDER BY timestamp DESC;", conn)
conn.close()

col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1.5])
with col_btn1:
    run_all_btn = st.button("🚀 Run All 40 Evaluation Cases", use_container_width=True)
with col_btn2:
    rerun_failed_btn = st.button("🔄 Re-Run Failed Cases", use_container_width=True)

if run_all_btn:
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    results = []
    for i, case in enumerate(test_cases):
        status_text.text(f"Executing Case {case['case_id']}: {case['title']}...")
        res = execute_evaluation_case(case)
        results.append(res)
        progress_bar.progress((i + 1) / len(test_cases))

    status_text.text("✅ All 40 test cases executed successfully!")
    st.success("Test evaluation suite completed! Results saved to persistent database.")
    st.rerun()

if rerun_failed_btn:
    # Identify failed cases from latest runs
    if len(runs_df) > 0:
        latest = runs_df.sort_values("timestamp").groupby("case_id").last().reset_index()
        failed_ids = latest[latest["passed"] == 0]["case_id"].tolist()
        if failed_ids:
            st.info(f"Re-running {len(failed_ids)} failed cases: {', '.join(failed_ids)}...")
            for case_id in failed_ids:
                case = next(c for c in test_cases if c["case_id"] == case_id)
                execute_evaluation_case(case)
            st.success("Failed cases re-executed!")
            st.rerun()
        else:
            st.success("🎉 All cases currently have passing status! Zero failed cases to re-run.")
    else:
        st.warning("No runs found in database. Run all 40 cases first.")

# Summary Metrics
if len(runs_df) > 0:
    latest_runs = runs_df.sort_values("timestamp").groupby("case_id").last().reset_index()
    total_run = len(latest_runs)
    passed_cnt = int(latest_runs["passed"].sum())
    failed_cnt = total_run - passed_cnt
    acc_pct = round((passed_cnt / max(1, total_run)) * 100.0, 1)

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        render_kpi_card("Evaluated Cases", f"{total_run}/40", "Full Labelled Suite", color_accent="#0F172A")
    with m2:
        render_kpi_card("Passed Cases", str(passed_cnt), f"{acc_pct}% Accuracy Rate", color_accent="#10B981")
    with m3:
        render_kpi_card("Failed Cases", str(failed_cnt), "Zero Tolerated" if failed_cnt == 0 else "Review Required", color_accent="#EF4444" if failed_cnt > 0 else "#10B981")
    with m4:
        render_kpi_card("Avg Processing Time", f"{latest_runs['processing_time_ms'].mean():.1f} ms", "Latency SLA: < 60,000 ms", color_accent="#0D9488")

st.markdown("---")

tab_diff, tab_all_cases, tab_raw_runs = st.tabs(["🔬 Side-by-Side Diff Inspector", "📋 40 Test Cases Definition", "📊 Run History Records"])

with tab_diff:
    st.subheader("Expected vs Actual Outcome Comparison")
    
    selected_case_id = st.selectbox(
        "Select Test Case to Inspect",
        [c["case_id"] for c in test_cases],
        format_func=lambda x: f"{x} — {next(c['title'] for c in test_cases if c['case_id'] == x)}"
    )
    case_def = next(c for c in test_cases if c["case_id"] == selected_case_id)
    
    if st.button(f"▶️ Run Single Case {selected_case_id}", use_container_width=True):
        with st.spinner("Executing case..."):
            res = execute_evaluation_case(case_def)
        st.success("Case executed!")
        st.rerun()

    # Compare side by side
    col_exp, col_act = st.columns(2)
    with col_exp:
        st.markdown("#### 🎯 Ground Truth Expectations")
        st.markdown(f"""
        <div class="callout-box" style="border-left-color: #0D9488;">
            <strong>Category:</strong> {case_def['category']}<br>
            <strong>Expected Classification:</strong> <code>{case_def['expected_classification']}</code><br>
            <strong>Expected Policy Rule:</strong> <code>{case_def['expected_policy_rule']}</code><br>
            <strong>Expected Outcome:</strong> {case_def['expected_workflow_outcome']}<br>
            <strong>Expected Exception:</strong> {case_def.get('expected_exception_handling') or 'None'}<br>
            <strong>Requires Human Approval:</strong> {'Yes' if case_def.get('expected_approval_requirement') else 'No'}
        </div>
        """, unsafe_allow_html=True)

    with col_act:
        st.markdown("#### ⚙️ Actual Measured Outcome")
        if len(runs_df) > 0 and selected_case_id in latest_runs["case_id"].values:
            actual_row = latest_runs[latest_runs["case_id"] == selected_case_id].iloc[0]
            passed_bool = bool(actual_row['passed'])
            box_color = "#10B981" if passed_bool else "#EF4444"
            
            st.markdown(f"""
            <div class="callout-box" style="border-left-color: {box_color};">
                <strong>Status:</strong> {'✅ PASSED' if passed_bool else '❌ FAILED'}<br>
                <strong>Measured Outcome:</strong> <code>{actual_row['actual_outcome']}</code><br>
                <strong>Routing Correct:</strong> {'Yes' if actual_row['routing_correctness'] else 'No'}<br>
                <strong>Exception Correct:</strong> {'Yes' if actual_row['exception_correctness'] else 'No'}<br>
                <strong>Processing Latency:</strong> <code>{actual_row['processing_time_ms']} ms</code><br>
                <strong>Errors:</strong> {actual_row['errors'] or 'None'}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("This case has not been executed yet. Click 'Run Single Case' above.")

    st.markdown("**Test Case Input Message:**")
    st.info(f"\"{case_def['input_message']}\"")

with tab_all_cases:
    st.subheader("Labelled Ground Truth Dataset (40 Cases)")
    cases_df = pd.DataFrame(test_cases)
    st.dataframe(cases_df[["case_id", "category", "title", "expected_classification", "expected_policy_rule", "expected_approval_requirement"]], use_container_width=True)
    
    st.download_button(
        "📥 Export 40 Test Cases to JSON",
        data=cases_df.to_json(orient="records", indent=2),
        file_name="alliance_40_test_cases.json",
        mime="application/json"
    )

with tab_raw_runs:
    st.subheader("Execution Run Logs (evaluation_runs table)")
    if len(runs_df) > 0:
        st.dataframe(runs_df[["run_id", "timestamp", "case_id", "expected_outcome", "actual_outcome", "routing_correctness", "passed", "processing_time_ms"]], use_container_width=True)
    else:
        st.info("No execution runs recorded yet.")
