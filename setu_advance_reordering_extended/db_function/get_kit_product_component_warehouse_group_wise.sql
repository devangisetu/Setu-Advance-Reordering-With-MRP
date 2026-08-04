DROP FUNCTION IF EXISTS public.get_kit_product_component_warehouse_group_wise(
    integer[],
    integer[],
    integer[],
    integer[],
    date,
    date
);

CREATE OR REPLACE FUNCTION public.get_kit_product_component_warehouse_group_wise(
    IN company_ids integer[],
    IN product_ids integer[],
    IN category_ids integer[],
    IN warehouse_ids integer[],
    IN start_date date,
    IN end_date date
)
RETURNS TABLE(
    product_id integer,
    product_name varchar,
    warehouse_id integer,
    sales_qty numeric,
    ads numeric
)
AS
$BODY$
DECLARE
    day_difference integer := ((end_date::date - start_date::date) + 1);
BEGIN

RETURN QUERY
SELECT
    sm.product_id,
    pt.name::varchar AS product_name,
    wh.id AS warehouse_id,
    SUM(sm.quantity) AS sales_qty,
    CASE
        WHEN day_difference > 0 AND SUM(sm.quantity) > 0
            THEN SUM(sm.quantity) / day_difference
        ELSE 0
    END AS ads
FROM stock_move sm
LEFT JOIN sale_order_line sol
    ON sm.sale_line_id = sol.id
LEFT JOIN stock_location sl
    ON sl.id = sm.location_id
LEFT JOIN product_product pp
    ON pp.id = sm.product_id
LEFT JOIN product_template pt
    ON pt.id = pp.product_tmpl_id
LEFT JOIN stock_warehouse wh
    ON wh.id = sl.warehouse_id
WHERE
    sm.state = 'done'
    AND sm.date::date BETWEEN start_date AND end_date
    AND sol.product_id != sm.product_id

    AND (
        company_ids IS NULL
        OR company_ids = '{}'
        OR sm.company_id = ANY(company_ids)
    )

    -- Component Product Filter
    AND (
        product_ids IS NULL
        OR product_ids = '{}'
        OR sol.product_id = ANY(product_ids)
    )

    -- Kit Product Category Filter
    AND (
        category_ids IS NULL
        OR category_ids = '{}'
        OR pt.categ_id = ANY(category_ids)
    )

    AND (
        warehouse_ids IS NULL
        OR warehouse_ids = '{}'
        OR sl.warehouse_id = ANY(warehouse_ids)
    )

GROUP BY
    sm.product_id,
    pt.name,
    wh.id;

END;
$BODY$
LANGUAGE plpgsql
VOLATILE
COST 100
ROWS 1000;