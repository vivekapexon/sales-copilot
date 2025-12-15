# queries.py
"""
Slim KPI SQL builder: 4 pre-call + 4 post-call KPIs (accurately mapped to actual schema).
"""

def escape(val: str) -> str:
    return val.replace("'", "''") if val else val


def kpi_overview_sql(username: str) -> str:
    uid = escape(username)

    return f"""
    WITH

    -- User → HCP mapping
    user_hcps AS (
        SELECT hcp_id
        FROM hcp_user_mapping
        WHERE user_id = '{uid}'
    ),

    -- PRE-CALL KPI #1: Total HCPs (GLOBAL)
    global_counts AS (
        SELECT COUNT(DISTINCT hcp_id) AS total_hcps_global
        FROM healthcare_data
    ),

    -- PRE-CALL KPI #2: Interacted HCPs
    user_interactions AS (
        SELECT COUNT(DISTINCT hm.hcp_id) AS interacted_hcps_count
        FROM history_mart hm
        JOIN user_hcps uh ON uh.hcp_id = hm.hcp_id
    ),

    -- PRE-CALL KPI #3 + POST-CALL KPI #3:
    -- IMPORTANT: Your followup_events has send_status = 'SCHEDULED'
    user_followups AS (
        SELECT
            SUM(CASE WHEN fe.send_status = 'SCHEDULED' THEN 1 ELSE 0 END) AS followups_sent_all_time,
            SUM(CASE WHEN fe.send_status = 'SCHEDULED'
                      AND fe.followup_sent_datetime >= CURRENT_DATE - 30
                THEN 1 ELSE 0 END) AS followups_sent_30d
        FROM followup_events fe
        JOIN user_hcps uh ON uh.hcp_id = fe.hcp_id
    ),

    -- PRE-CALL KPI #4: Scheduled next 7 days
    user_scheduled_calls AS (
        SELECT
            COUNT(DISTINCT hd.hcp_id) AS total_hcps_assigned,
            COALESCE(SUM(hd.scheduled_calls_next_7d_cnt), 0) AS scheduled_calls_next_7d
        FROM healthcare_data hd
        JOIN user_hcps uh ON uh.hcp_id = hd.hcp_id
    ),

    -- POST-CALL KPI #1 & #2
    user_action_items AS (
        SELECT
            SUM(CASE WHEN cai.task_due_date >= CURRENT_DATE THEN 1 ELSE 0 END) AS action_items_pending,
            SUM(CASE WHEN cai.task_due_date >= CURRENT_DATE - 30
                     THEN COALESCE(cai.sample_request_qty, 0) ELSE 0 END) AS sample_request_qty_30d
        FROM call_action_items cai
        JOIN user_hcps uh ON uh.hcp_id = cai.hcp_id
    ),

    -- POST-CALL KPI #4 (transcripts today)
    -- NOTE: Your sample rows have NULL call_datetime_local.
    -- So this yields 0 unless future data contains timestamps.
    user_voice AS (
        SELECT
            COUNT(*) AS transcripts_today
        FROM voice_to_crm v
        JOIN user_hcps uh ON uh.hcp_id = v.hcp_id
        WHERE DATE(v.call_datetime_local) = CURRENT_DATE
    )

    SELECT
        gc.total_hcps_global,

        -- PRE-CALL (4 KPIs)
        usc.total_hcps_assigned,
        COALESCE(ui.interacted_hcps_count, 0) AS total_interacted_hcps_by_user,
        COALESCE(uf.followups_sent_all_time, 0) AS followup_emails_sent_by_user,
        COALESCE(usc.scheduled_calls_next_7d, 0) AS scheduled_calls_next_7d,

        -- POST-CALL (4 KPIs)
        COALESCE(uai.action_items_pending, 0) AS action_items_pending,
        COALESCE(uai.sample_request_qty_30d, 0) AS sample_request_qty_30d,
        COALESCE(uf.followups_sent_30d, 0) AS followups_sent_last_30d,
        COALESCE(uv.transcripts_today, 0) AS total_hcp_contacted_today

    FROM global_counts gc
    LEFT JOIN user_scheduled_calls usc ON TRUE
    LEFT JOIN user_interactions ui ON TRUE
    LEFT JOIN user_followups uf ON TRUE
    LEFT JOIN user_action_items uai ON TRUE
    LEFT JOIN user_voice uv ON TRUE
    LIMIT 1;
    """
