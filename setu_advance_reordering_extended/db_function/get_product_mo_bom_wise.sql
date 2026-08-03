DROP FUNCTION IF EXISTS public.get_product_mo_bom_wise(
    integer[],
    integer[],
    integer[],
    date,
    date
);

DROP FUNCTION IF EXISTS public.get_product_mo_bom_wise(
    integer[],
    integer[],
    integer[],
    integer[],
    integer[],
    date,
    date
);

CREATE OR REPLACE FUNCTION public.get_product_mo_bom_wise(
    IN company_ids integer[],
    IN product_ids integer[],
    IN category_ids integer[],
    IN warehouse_ids integer[],
    IN bom_ids integer[],
    IN start_date date,
    IN end_date date
)
RETURNS TABLE(
    product_id integer,
    bom_id integer,
    mo_ids integer[]
)
AS
$BODY$
BEGIN

RETURN QUERY
SELECT
    mp.product_id,
    mp.bom_id,
    ARRAY_AGG(mp.id ORDER BY mp.id) AS mo_ids

FROM mrp_production mp
INNER JOIN product_product pp
    ON pp.id = mp.product_id
INNER JOIN product_template pt
    ON pt.id = pp.product_tmpl_id
LEFT JOIN stock_picking_type spt
    ON spt.id = mp.picking_type_id

WHERE
    mp.state != 'cancel'
    AND mp.date_start::date BETWEEN start_date AND end_date

    AND (
        company_ids IS NULL
        OR company_ids = '{}'
        OR mp.company_id = ANY(company_ids)
    )

    AND (
        product_ids IS NULL
        OR product_ids = '{}'
        OR mp.product_id = ANY(product_ids)
    )

    AND (
        category_ids IS NULL
        OR category_ids = '{}'
        OR pt.categ_id = ANY(category_ids)
    )

    AND (
        warehouse_ids IS NULL
        OR warehouse_ids = '{}'
        OR spt.warehouse_id = ANY(warehouse_ids)
    )

    AND (
        bom_ids IS NULL
        OR bom_ids = '{}'
        OR mp.bom_id = ANY(bom_ids)
    )

GROUP BY
    mp.product_id,
    mp.bom_id;

END;
$BODY$
LANGUAGE plpgsql
VOLATILE
COST 100
ROWS 1000;
