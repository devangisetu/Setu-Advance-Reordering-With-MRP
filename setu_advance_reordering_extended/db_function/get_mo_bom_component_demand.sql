DROP FUNCTION IF EXISTS public.get_mo_bom_component_demand(integer[], integer[], integer[], date, date);
CREATE OR REPLACE FUNCTION public.get_mo_bom_component_demand(
    IN parent_product_ids integer[],
    IN component_product_ids integer[],
    IN warehouse_ids integer[],
    IN start_date date,
    IN end_date date)
    RETURNS TABLE(
        mo_id integer,
        mo_main_product_id integer,
        component_product_id integer,
        required_qty numeric
    ) AS
$BODY$
BEGIN
    RETURN QUERY
    SELECT
        mp.id AS mo_id,
        mp.product_id AS mo_main_product_id,
        sm.product_id AS component_product_id,
        COALESCE(SUM(sm.product_uom_qty), 0) AS required_qty
    FROM mrp_production mp
        INNER JOIN stock_move sm ON sm.raw_material_production_id = mp.id
        LEFT JOIN stock_picking_type spt ON spt.id = mp.picking_type_id
    WHERE mp.state = 'draft'
        AND mp.date_start IS NOT NULL
        AND mp.date_finished IS NOT NULL
        AND mp.date_start::date >= start_date
        AND mp.date_finished::date <= end_date
        AND (
            COALESCE(array_length(parent_product_ids, 1), 0) < 1
            OR mp.product_id = ANY(parent_product_ids)
        )
        AND sm.raw_material_production_id IS NOT NULL
        AND sm.state != 'cancel'
        AND (
            COALESCE(array_length(component_product_ids, 1), 0) < 1
            OR sm.product_id = ANY(component_product_ids)
        )
        AND (
            COALESCE(array_length(warehouse_ids, 1), 0) < 1
            OR spt.warehouse_id = ANY(warehouse_ids)
        )
    GROUP BY mp.id, mp.product_id, sm.product_id;
END;
$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100
  ROWS 1000;
