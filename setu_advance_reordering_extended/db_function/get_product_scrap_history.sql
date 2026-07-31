DROP FUNCTION IF EXISTS public.get_product_scrap_history(integer[], date, date);
CREATE OR REPLACE FUNCTION public.get_product_scrap_history(
    IN orderpoint_ids integer[],
    IN start_date_val date,
    IN end_date_val date
)
RETURNS TABLE(
    orderpoint_id integer,
    product_id integer,
    warehouse_id integer,
    start_date date,
    end_date date,
    duration integer,
    scrap_qty numeric,
    average_daily_scrap numeric,
    maximum_daily_scrap numeric,
    minimum_daily_scrap numeric
) AS
$BODY$
BEGIN
    RETURN QUERY
    WITH periods AS (
        SELECT 
            id AS period_id,
            fpstartdate AS p_start,
            fpenddate AS p_end,
            COALESCE(NULLIF((fpenddate - fpstartdate) + 1, 0), 1) AS p_duration
        FROM reorder_fiscalperiod
        WHERE fpstartdate >= start_date_val AND fpstartdate <= end_date_val
    ),
    orderpoints AS (
        SELECT 
            op.id AS orderpoint_id,
            op.product_id,
            op.warehouse_id
        FROM stock_warehouse_orderpoint op
        WHERE op.id = ANY(orderpoint_ids)
    ),
    op_periods AS (
        SELECT 
            op.orderpoint_id,
            op.product_id,
            op.warehouse_id,
            p.period_id,
            p.p_start,
            p.p_end,
            p.p_duration
        FROM orderpoints op
        CROSS JOIN periods p
    ),
    scrap_moves AS (
        SELECT 
            sm.id AS move_id,
            sm.product_id,
            sm.product_qty,
            sm.date::date AS move_date,
            COALESCE(
                source_loc.warehouse_id,
                sm.warehouse_id,
                spt.warehouse_id,
                source_wh.id
            ) AS wh_id
        FROM stock_move sm
        INNER JOIN stock_location source_loc ON source_loc.id = sm.location_id
        INNER JOIN stock_location dest_loc ON dest_loc.id = sm.location_dest_id
        LEFT JOIN stock_picking_type spt ON spt.id = sm.picking_type_id
        LEFT JOIN stock_warehouse source_wh ON source_loc.parent_path::text ~~ concat('%/', source_wh.view_location_id, '/%')
        WHERE sm.state = 'done'
          AND dest_loc.scrap_location = TRUE
          AND sm.product_id IN (SELECT op.product_id FROM orderpoints op)
    ),
    daily_totals AS (
        SELECT 
            op.orderpoint_id,
            op.period_id,
            sm.move_date,
            SUM(sm.product_qty) AS daily_qty
        FROM op_periods op
        INNER JOIN scrap_moves sm ON sm.product_id = op.product_id AND sm.wh_id = op.warehouse_id
        WHERE sm.move_date >= op.p_start AND sm.move_date <= op.p_end
        GROUP BY 
            op.orderpoint_id,
            op.period_id,
            sm.move_date
    ),
    period_metrics AS (
        SELECT 
            dt.orderpoint_id,
            dt.period_id,
            SUM(dt.daily_qty) AS total_scrap,
            MAX(dt.daily_qty) AS max_daily,
            MIN(NULLIF(dt.daily_qty, 0)) AS min_daily
        FROM daily_totals dt
        GROUP BY 
            dt.orderpoint_id,
            dt.period_id
    )
    SELECT 
        op.orderpoint_id,
        op.product_id,
        op.warehouse_id,
        op.p_start AS start_date,
        op.p_end AS end_date,
        op.p_duration AS duration,
        COALESCE(pm.total_scrap, 0.0)::numeric AS scrap_qty,
        ROUND(COALESCE(pm.total_scrap, 0.0) / op.p_duration, 2)::numeric AS average_daily_scrap,
        COALESCE(pm.max_daily, 0.0)::numeric AS maximum_daily_scrap,
        COALESCE(pm.min_daily, 0.0)::numeric AS minimum_daily_scrap
    FROM op_periods op
    LEFT JOIN period_metrics pm ON pm.orderpoint_id = op.orderpoint_id AND pm.period_id = op.period_id;

END; $BODY$
LANGUAGE plpgsql VOLATILE
COST 100
ROWS 1000;
