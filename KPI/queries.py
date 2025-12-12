# queries.py
"""
Slim KPI SQL builder: 4 pre-call + 4 post-call KPIs (user-scoped),
with unambiguous aliases and minimal work.
"""

def escape(val: str) -> str:
    return val.replace("'", "''") if val is not None else None


def kpi_overview_sql(user_id: str) -> str:
    uid = escape(user_id)
    return f"""
    WITH
    base AS (
        SELECT
            hd.hcp_id,
            hd.territory_id,
            COALESCE(hd.scheduled_calls_next_7d_cnt, 0) AS scheduled_calls_next_7d
        FROM healthcare_data hd
    ),

    user_hcps AS (
        SELECT hum.hcp_id
        FROM hcp_user_mapping hum
        WHERE hum.user_id = '{uid}'
    ),

    -- Pre-call: interactions and followups
    user_interactions AS (
        SELECT
            COUNT(DISTINCT hm.hcp_id) AS interacted_hcps_count
        FROM history_mart hm
        JOIN user_hcps uh ON uh.hcp_id = hm.hcp_id
    ),

    user_followups AS (
        SELECT
            SUM(CASE WHEN fe.send_status = 'sent' THEN 1 ELSE 0 END) AS followups_sent_all_time,
            SUM(CASE WHEN fe.followup_sent_datetime >= CURRENT_DATE - 30 AND fe.send_status = 'sent' THEN 1 ELSE 0 END) AS followups_sent_30d
        FROM followup_events fe
        JOIN user_hcps uh ON uh.hcp_id = fe.hcp_id
    ),

    -- Post-call: action items, samples, transcripts
    user_action_items AS (
        SELECT
            SUM(CASE WHEN cai.task_due_date >= CURRENT_DATE THEN 1 ELSE 0 END) AS action_items_pending,
            SUM(CASE WHEN cai.task_due_date >= CURRENT_DATE - 30 THEN COALESCE(cai.sample_request_qty,0) ELSE 0 END) AS samples_requested_30d,
            COUNT(DISTINCT cai.hcp_id) AS hcps_with_action_items
        FROM call_action_items cai
        JOIN user_hcps uh ON uh.hcp_id = cai.hcp_id
    ),

    user_voice AS (
        SELECT
            COUNT(CASE WHEN DATE(v.call_datetime_local) = CURRENT_DATE THEN 1 END) AS voice_count_today
        FROM voice_to_crm v
        JOIN user_hcps uh ON uh.hcp_id = v.hcp_id
    ),

    user_healthcare_agg AS (
        SELECT
            COUNT(DISTINCT b.hcp_id) AS total_hcps_assigned,
            COALESCE(SUM(b.scheduled_calls_next_7d),0) AS scheduled_calls_next_7d
        FROM (
            SELECT hd.hcp_id, COALESCE(hd.scheduled_calls_next_7d_cnt,0) AS scheduled_calls_next_7d
            FROM healthcare_data hd
        ) b
        JOIN user_hcps uh ON uh.hcp_id = b.hcp_id
    ),

    global_counts AS (
        SELECT
            COUNT(DISTINCT hd.hcp_id) AS total_hcps_global,
            COUNT(DISTINCT hd.territory_id) AS total_territories_global
        FROM healthcare_data hd
    )

    SELECT
        gc.total_hcps_global,
        gc.total_territories_global,

        -- pre-call user-scoped
        uha.total_hcps_assigned,
        COALESCE(ui.interacted_hcps_count,0) AS total_interacted_hcps_by_user,
        COALESCE(uf.followups_sent_all_time,0) AS followup_emails_sent_by_user,
        COALESCE(uha.scheduled_calls_next_7d,0) AS scheduled_calls_next_7d,

        -- post-call user-scoped
        COALESCE(uai.action_items_pending,0) AS action_items_pending,
        COALESCE(uai.samples_requested_30d,0) AS sample_request_qty_30d,
        COALESCE(uf.followups_sent_30d,0) AS followups_sent_last_30d,
        COALESCE(uv.voice_count_today,0) AS transcripts_count_today

    FROM global_counts gc
    LEFT JOIN user_healthcare_agg uha ON TRUE
    LEFT JOIN user_interactions ui ON TRUE
    LEFT JOIN user_followups uf ON TRUE
    LEFT JOIN user_action_items uai ON TRUE
    LEFT JOIN user_voice uv ON TRUE
    LIMIT 1;
    """
