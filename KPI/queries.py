"""
KPI SQL builder
- No schema changes
- Safe for shared pipelines
- Correct KPI aggregation
"""

def escape(val: str) -> str:
    return val.replace("'", "''") if val else val


def kpi_overview_sql(username: str) -> str:
    uid = escape(username)

    return f"""
    WITH
    -- User → HCP mapping (foundation)
    user_hcps AS (
        SELECT DISTINCT hcp_id
        FROM hcp_user_mapping
        WHERE user_id = '{uid}'
    ),

    -- Guard: detect no mapping
    has_mapping AS (
        SELECT COUNT(*) AS cnt FROM user_hcps
    ),

    -- Latest healthcare snapshot per HCP
    latest_hd AS (
        SELECT hcp_id, MAX(as_of_date) AS max_date
        FROM healthcare_data
        GROUP BY hcp_id
    )

    SELECT
        -- GLOBAL
        (SELECT COUNT(DISTINCT hcp_id) FROM healthcare_data)
            AS total_hcps_global,

        -- PRE-CALL KPIs
        (SELECT COUNT(*) FROM user_hcps)
            AS total_hcps_assigned,

        (SELECT COUNT(DISTINCT hm.hcp_id)
         FROM history_mart hm
         JOIN user_hcps uh ON uh.hcp_id = hm.hcp_id
        ) AS total_interacted_hcps_by_user,

        (SELECT COUNT(*)
         FROM followup_events fe
         JOIN user_hcps uh ON uh.hcp_id = fe.hcp_id
         WHERE fe.send_status = 'SCHEDULED'
        ) AS followup_emails_sent_by_user,

        (SELECT COALESCE(SUM(hd.scheduled_calls_next_7d_cnt), 0)
         FROM healthcare_data hd
         JOIN latest_hd l
           ON hd.hcp_id = l.hcp_id
          AND hd.as_of_date = l.max_date
         JOIN user_hcps uh
           ON uh.hcp_id = hd.hcp_id
        ) AS scheduled_calls_next_7d,

        -- POST-CALL KPIs
        (SELECT COUNT(*)
         FROM call_action_items cai
         JOIN user_hcps uh ON uh.hcp_id = cai.hcp_id
         WHERE cai.task_due_date >= CURRENT_DATE - 1
        ) AS action_items_pending,

        (SELECT COALESCE(SUM(cai.sample_request_qty), 0)
         FROM call_action_items cai
         JOIN user_hcps uh ON uh.hcp_id = cai.hcp_id
         WHERE cai.sample_request_qty > 0
           AND cai.task_due_date >= CURRENT_DATE - 30
        ) AS sample_request_qty_30d,

        (SELECT COUNT(*)
         FROM followup_events fe
         JOIN user_hcps uh ON uh.hcp_id = fe.hcp_id
         WHERE fe.send_status = 'SCHEDULED'
           AND DATE(fe.followup_sent_datetime) >= CURRENT_DATE - 30
        ) AS followups_sent_last_30d,

        (SELECT COUNT(DISTINCT hm.hcp_id)
         FROM history_mart hm
         JOIN user_hcps uh ON uh.hcp_id = hm.hcp_id
         WHERE hm.call_date = CURRENT_DATE
        ) AS total_hcp_contacted_today

    FROM has_mapping
    WHERE has_mapping.cnt > 0;
    """
