DROP FUNCTION IF EXISTS public.get_mo_planning_data(integer[], integer[], date, date);
CREATE OR REPLACE FUNCTION public.get_mo_planning_data(
    IN product_ids integer[],
    IN warehouse_ids integer[],
    IN start_date date,
    IN end_date date)
    RETURNS TABLE(
        product_id integer,
        production_out_demand numeric,
        production_in_demand numeric,
        in_production numeric,
        out_production numeric
    ) AS
$BODY$
BEGIN
    RETURN QUERY
    WITH requested_products AS (
        SELECT DISTINCT unnest(product_ids) AS product_id
    ),
    filtered_mos AS (
        SELECT
            mp.id,
            mp.product_id,
            mp.product_qty,
            mp.state
        FROM mrp_production mp
            LEFT JOIN stock_picking_type spt ON spt.id = mp.picking_type_id
        WHERE mp.state IN ('draft')
            AND mp.date_start IS NOT NULL
            AND mp.date_finished IS NOT NULL
            AND mp.date_start::date >= start_date
            AND mp.date_finished::date <= end_date
            AND (
                COALESCE(array_length(warehouse_ids, 1), 0) < 1
                OR spt.warehouse_id = ANY(warehouse_ids)
            )
    ),
    mo_out AS (
        SELECT
            fm.product_id,
            COALESCE(SUM(fm.product_qty), 0) AS qty
        FROM filtered_mos fm
        WHERE (
            COALESCE(array_length(product_ids, 1), 0) < 1
            OR fm.product_id = ANY(product_ids)
        )
        GROUP BY fm.product_id
    ),
    mo_incoming AS (
        SELECT
            mp.product_id,
            COALESCE(SUM(
                GREATEST(
                    mp.product_qty - COALESCE(produced.qty, 0),
                    0
                )
            ), 0) AS qty
        FROM mrp_production mp
            LEFT JOIN stock_picking_type spt ON spt.id = mp.picking_type_id
            LEFT JOIN LATERAL (
                SELECT COALESCE(SUM(sm.quantity), 0) AS qty
                FROM stock_move sm
                WHERE sm.production_id = mp.id
                    AND sm.product_id = mp.product_id
                    AND sm.state != 'cancel'
                    AND sm.picked IS TRUE
            ) produced ON TRUE
        WHERE mp.state IN ('confirmed', 'progress', 'to_close')
            AND mp.date_start IS NOT NULL
            AND mp.date_finished IS NOT NULL
            AND mp.date_start::date >= start_date
            AND mp.date_finished::date <= end_date
            AND (
                COALESCE(array_length(product_ids, 1), 0) < 1
                OR mp.product_id = ANY(product_ids)
            )
            AND (
                COALESCE(array_length(warehouse_ids, 1), 0) < 1
                OR spt.warehouse_id = ANY(warehouse_ids)
            )
        GROUP BY mp.product_id
    ),
    mo_outgoing AS (
        select
            sml.product_id,
            sum(sml.quantity) as qty
        from stock_move_line  sml
        join stock_move sm on sm.id = sml.move_id
        LEFT JOIN stock_picking_type spt ON spt.id = sm.picking_type_id
        where sm.raw_material_production_id is not null and sml.state not in ('done','cancel')
        AND (
                        COALESCE(array_length(product_ids, 1), 0) < 1
                        OR sml.product_id = ANY(product_ids)
                    )
                    AND (
                        COALESCE(array_length(warehouse_ids, 1), 0) < 1
                        OR spt.warehouse_id = ANY(warehouse_ids)
                    )
        GROUP BY sml.product_id
    ),
    mo_component AS (
        SELECT
            sm.product_id,
            COALESCE(SUM(sm.product_uom_qty), 0) AS qty
        FROM mrp_production mp
            INNER JOIN stock_move sm ON sm.raw_material_production_id = mp.id
            LEFT JOIN stock_picking_type spt ON spt.id = mp.picking_type_id
        WHERE mp.state IN ('draft')
            AND mp.date_start IS NOT NULL
            AND mp.date_finished IS NOT NULL
            AND mp.date_start::date >= start_date
            AND mp.date_finished::date <= end_date
            AND sm.raw_material_production_id IS NOT NULL
            AND sm.state != 'cancel'
            AND (
                COALESCE(array_length(product_ids, 1), 0) < 1
                OR sm.product_id = ANY(product_ids)
            )
            AND (
                COALESCE(array_length(warehouse_ids, 1), 0) < 1
                OR spt.warehouse_id = ANY(warehouse_ids)
            )
        GROUP BY sm.product_id
    )
    SELECT
        rp.product_id,
        COALESCE(mo_out.qty, 0) AS production_out_demand,
        COALESCE(mo_component.qty, 0) AS production_in_demand,
        COALESCE(mo_outgoing.qty, 0) AS in_production,
        COALESCE(mo_incoming.qty, 0) AS out_production
    FROM requested_products rp
        LEFT JOIN mo_out ON mo_out.product_id = rp.product_id
        LEFT JOIN mo_component ON mo_component.product_id = rp.product_id
        LEFT JOIN mo_incoming ON mo_incoming.product_id = rp.product_id
        LEFT JOIN mo_outgoing ON mo_outgoing.product_id = rp.product_id;
END;
$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100
  ROWS 1000;
