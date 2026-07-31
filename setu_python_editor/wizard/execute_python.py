# -*- coding:utf-8 -*-
from odoo import models, fields, _, api, Command
import pandas
from odoo.exceptions import ValidationError

import logging

_logger = logging.getLogger(__name__)

try:
    import xlrd

    try:
        from xlrd import xlsx
    except ImportError:
        xlsx = None
except ImportError:
    xlrd = xlsx = None


# from odoo.tools.safe_eval import safe_eval
class SetuPythonEditor(models.Model):
    _name = "setu.python.editor"
    _description = "setu.python.editor"

    name = fields.Char(string='Name', size=1024, required=True)
    code = fields.Text(string='Python Code')
    result = fields.Text(string='Result')
    editor_type = fields.Selection([('python', 'Python'), ('sql', 'PSQL')],
                                   string='Editor Type', required=True, default='python')

    def get_code(self):
        return {'code': self.code, 'output': self.result, 'self': self.id, 'name': self.name, 'editor_type': self.editor_type}

    def execute_code(self, args=False):
        if self.editor_type == 'python':
            if args:
                self.code = args[0]
                self.result = args[1]
            localdict = {'self': self, 'user_obj': self.env.user}
            for obj in self:
                try:
                    res = exec(obj.code, localdict)
                    if localdict.get('result', False):
                        self.write({'result': localdict['result']})
                        return self.result
                    else:
                        self.write({'result': ''})
                        return self.result
                except Exception as e:
                    return e
        else:
            if args:
                self.code = args[0]
                self.result = args[1]
                try:
                    query = self.code
                    self._cr.execute(query)
                    if 'update' in query or 'Update' in query:
                        self.write({'result': 'Update Successfully'})
                        return 'Update Successfully'
                        pass
                    if 'delete' in query or 'Delete' in query:
                        self.write({'result': 'Deleted Successfully'})
                        return 'Deleted Successfully'
                        pass
                    if 'Truncate' in query or 'truncate' in query:
                        self.write({'result': 'Truncate Successfully'})
                        return 'Truncate Successfully'
                        pass

                    datas = self._cr.dictfetchall()
                    df = pandas.DataFrame(datas)
                    datas = df.to_html(table_id='output_ed', index=False)
                    self.write({'result': datas})
                    return datas
                except Exception as e:
                    raise ValidationError(e)

    def test(self):
        # user = self.env['res.users'].browse(2)
        # user.write({'company_ids': self.env['res.company'].search([]).ids})
        import random
        products_list = [
            "Potato",
            "Salt",
            "Chilli",
            "Spices",
            "Tomato",
            "Chaat",
            "Pudina",
            "Cream",
            "Herbs",
            "Onion",
            "Cheese",
            "Oregano",
            "Pizza",
            "Besan",
            "Banana",
            "Black Pepper",
            "MAGDAL"
        ]
        item_owners = self.env.ref('setu_tender_management.setu_tender_rights_group_manager').users - self.env['res.users'].browse([2,37])
        companies = self.env.user.company_ids
        for company in companies.filtered(lambda c:c.parent_id):
            users = random.sample(item_owners.ids, 3)
            users = self.env['res.users'].browse(users)
            users.write({'company_id': company.id, 'company_ids': [(6, 0, company.ids)]})
            item_owners = item_owners - users
            for p in products_list:
                product = self.env['product.product'].with_company(company).search([('name', '=', p)])
                product.write({
                    'owner_id': random.sample(users.ids, 1)[0],
                    'rfq_approver_ids': [(6, 0, [37])]})

    def create_supplier_partner(self,attachment_id):

        file_data = self.read_file(attachment_id)
        vendor_data_vals = []
        vendor_ids = []
        not_created_partner = []
        for data in file_data.get('data'):
            vals = {}
            country_id = self.env['res.country'].search([('code','=','IN')])
            state_id = self.env['res.country.state'].search([('name','=',data.get('State/State Name')),('country_id','=',country_id.id if country_id else False)])
            al_email_vals = []
            if data.get('AL Email', '') and data.get('AL Email') != 'NULL':
                for mail in data.get('AL Email').split(','):
                    al_email_vals.append(Command.create({
                        'name': mail,
                        'is_active': True
                    }))
            al_phone_vals = []
            if data.get('AL Phone','') and data.get('AL Phone') != 'NULL':
                for phone in data.get('AL Phone').split(','):
                    al_phone_vals.append(Command.create({
                        'name': phone,
                        'is_active': True
                    }))
            vals.update({ 'vendor_sap_reference': data.get('SupCode'),
                'company_name': data.get('Company Name'),
                'name': data.get('Name'),
                'email': data.get('Email'),
                'vendor_email_ids': al_email_vals,
                'mobile': data.get('Phone'),
                'vendor_mobile_ids': al_phone_vals,
                'state_id': state_id.id if state_id else False,
                'country_id': country_id.id if country_id else False,
                'city': data.get('City'),
                'supplier_rank':1})

            if data.get('Tax ID') and data.get('Tax ID') != 'NOT GST' and data.get('Tax ID') != 'NO GST':
                vals.update({'vat': data.get('Tax ID') if data.get('Tax ID') != 'NO GST' else False,})
            vendor_data_vals.append(vals)
        partner_obj = self.env['res.partner']

        for value in vendor_data_vals:
            try:
                supplier = partner_obj.create(value)
                vendor_ids.append(supplier.id)
            except Exception:
                # vendor_ids.append(supplier.id)
                not_created_partner.append(value.get('email'))
                _logger.info(value)
        print('vendor_ids',vendor_ids)
        print('not_created',not_created_partner)
        for partner in vendor_ids:
            self.env['res.partner'].browse(partner).action_create_user_for_portal()
        print(not_created_partner)
        return vendor_ids


    def update_supplier(self,attachment_id):
        file_data = self.read_file(attachment_id)
        print(len(file_data.get('data')))
        total_partner = []
        partner_not_in_instance = []

        for data in file_data.get('data'):
            al_phone_vals = []
            mobile = ""
            if data.get('Mobile', '') and data.get('Mobile') != 'NULL':
                mobile = data.get('Mobile', '').split(',')[0]
                for phone in data.get('Mobile').split(',')[1:]:
                    al_phone_vals.append(Command.create({
                        'name': phone,
                        'is_active': True
                    }))
            partner_obj = self.env['res.partner'].search([('vendor_sap_reference','=',data.get('SupCode'))])
            if partner_obj:
                vals = {
                    'email':data.get('email'),
                     'vendor_mobile_ids': al_phone_vals,
                    'mobile':mobile
                }
                partner_obj.write(vals)
                total_partner.append(partner_obj)
            else:
                partner_not_in_instance.append(data.get('SupCode'))
        print(total_partner)
        print(partner_not_in_instance)



    def read_file(self, attachment):
        '''
            Read selected file to import inbound shipment report and return Reader to the caller
        '''
        attachment_id = self.env['ir.attachment'].browse(attachment)
        reader = []
            # raise ValidationError(_("The file must have an extension .csv Format"))
        if attachment_id.raw:
            reader = {}
            try:
                book = xlrd.open_workbook(file_contents=attachment_id.raw or b'')
                sheet = book.sheet_by_index(0)
            except Exception as e:
                raise ValidationError(
                    _("Error '{}' comes at the time of reading attachment {}".format(e, attachment_id.name)))
            header = []
            data = []
            for col in range(sheet.ncols):
                header.append(sheet.cell_value(0, col))

            # transform the workbook to a list of dictionaries
            for row in range(1, sheet.nrows):
                elements = {}
                for col in range(sheet.ncols):
                    cell_value = sheet.cell_value(row, col)
                    elements[header[col]] = cell_value
                data.append(elements)
            reader.update({'file_header': header, 'data': data})
        else:
            raise ValidationError(_("No data available in .XLSX file"))

        return reader

    def set_prod_suppiers(self, attachment_id):
        data = self.read_file(attachment_id)
        prod_data = data.get('data')
        product_data = []
        not_found_product_data = []
        vendor_data = []
        not_found_vendor_data = []
        plats_data = []
        not_found_plats_data = []
        supplier_ids = []

        prod_obj = self.env['product.template'].sudo()
        company_obj = self.env['res.company'].sudo()
        parner_obj = self.env['res.partner'].sudo()
        product_supplier_obj = self.env['product.supplierinfo'].sudo()
        duplicate_prod = []
        for data in prod_data:
            product = False
            vendor = False
            prod = data.get('prod_sap_code')
            if type(prod) == float:
                prod = str(int(prod))
            vend = data.get('vendor_sap_code')
            if type(vend) == float:
                vend = str(int(vend))
            product = prod_obj.search([('default_code', '=', prod)], limit=1)
            if len(product) > 1:
                duplicate_prod.append(prod)
            vendor = parner_obj.search([('vendor_sap_reference', '=', vend)],limit=1)
            if product:
                if prod not in product_data:
                    product_data.append(prod)
            else:
                if prod not in not_found_product_data:
                    not_found_product_data.append(prod)

            if vendor:
                if vend not in vendor_data:
                    vendor_data.append(vend)
            else:
                if vend not in not_found_vendor_data:
                    not_found_vendor_data.append(vend)
            if product and vendor:
                comapny_ids = []
                plant_data = data.get('prod_vendor_plants')
                for plant in plant_data.split(', '):
                    company = company_obj.search([('code', '=', plant)],limit=1)
                    if company:
                        comapny_ids.append(company.id)
                supplier = product_supplier_obj.create(
                    {'product_tmpl_id': product.id, 'partner_id': vendor.id, 'plant_ids': [(6, 0, comapny_ids)]})
                supplier_ids.append(supplier.id)
        result = supplier_ids
        print(duplicate_prod)
        return result


    def block_vendor(self,attachment_id):
        file_data = self.read_file(attachment_id)
        vendor_data = file_data.get('data')
        vendor_block_data = []
        for data in vendor_data:
            prod = False
            vend = False
            reason = False
            prod = data.get('prod')
            if type(prod) == float:
                prod = str(int(prod))
            vend = data.get('vendor')
            if type(vend) == float:
                vend = str(int(vend))
            # reason = data.get('reason')

            prod_obj = self.env['product.template'].sudo()
            partner_obj = self.env['res.partner'].sudo()
            product_supplier_obj = self.env['product.supplierinfo'].sudo()
            product = False
            vendor = False
            product_supplier = False
            product = prod_obj.search([('default_code', '=', prod)], limit=1)
            vendor = partner_obj.search([('vendor_sap_reference', '=', vend)], limit=1)
            product_supplier = product_supplier_obj.search(
                [('product_tmpl_id', '=', product.id), ('partner_id', '=', vendor.id)])
            if product_supplier:
                for rec in product_supplier:
                    rec.write({'is_blocked_vendor': True})
                # vendor.blocked_reason = reason
            vendor_block_data.append(vendor.name)
        print(vendor_block_data)
        return True


    def set_item_owner(self):
        product_owner = product_owner = [
            {'ItemCode': 300156.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300157.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300158.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': 'HMS', 'BW08': 'HMS'}, {'ItemCode': 300159.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300160.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300161.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300163.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300164.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300165.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300170.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300171.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300172.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300173.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300174.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300175.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300176.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300177.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300178.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300179.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300182.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300183.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300184.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300185.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300186.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300189.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300190.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': 'HMS', 'BW08': 'HMS'}, {'ItemCode': 300193.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300194.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300195.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300196.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300197.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300198.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300199.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300200.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300201.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300202.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300203.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300204.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300205.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300206.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300207.0, 'BW01': '', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300208.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300209.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300212.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300215.0, 'BW01': '', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300219.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300220.0, 'BW01': 'HMS', 'BW04': '', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300222.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300225.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300228.0, 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300230.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300232.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300235.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300237.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': 'HMS', 'BW08': ''}, {'ItemCode': 300238.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300240.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300241.0, 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300245.0, 'BW01': '', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300249.0, 'BW01': 'HMS', 'BW04': '', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300251.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': 'HMS', 'BW08': ''}, {'ItemCode': 300252.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300253.0, 'BW01': '', 'BW04': 'HMS', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300254.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': 'HMS', 'BW08': 'HMS'}, {'ItemCode': 300255.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': 'HMS', 'BW08': 'HMS'}, {'ItemCode': 300257.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300258.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': 'HMS', 'BW08': 'HMS'}, {'ItemCode': 300259.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300261.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300266.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300267.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300272.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300273.0, 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300279.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300281.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': 'HMS', 'BW08': ''}, {'ItemCode': 300282.0, 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300283.0, 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300289.0, 'BW01': '', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300290.0, 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300292.0, 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300293.0, 'BW01': '', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300299.0, 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300300.0, 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300306.0, 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300307.0, 'BW01': '', 'BW04': '', 'BW07': '', 'BW10': 'HMS', 'BW08': ' '}, {'ItemCode': 300308.0, 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300310.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': ' ', 'BW08': ' '}, {'ItemCode': 300313.0, 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300315.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': 'HMS', 'BW08': ''}, {'ItemCode': 300316.0, 'BW01': 'HMS', 'BW04': '', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300319.0, 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300320.0, 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300321.0, 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300322.0, 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300323.0, 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300324.0, 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300325.0, 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300327.0, 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300328.0, 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300329.0, 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300331.0, 'BW01': '', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300332.0, 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300333.0, 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300334.0, 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300338.0, 'BW01': '', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300339.0, 'BW01': '', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300340.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300342.0, 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300343.0, 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300344.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': 'HMS', 'BW08': 'HMS'}, {'ItemCode': 300223.0, 'BW01': '', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300291.0, 'BW01': '', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 600000.0, 'BW01': '', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300355.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300359.0, 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300360.0, 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300364.0, 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300365.0, 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300376.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300377.0, 'BW01': '', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300378.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': 'HMS', 'BW08': 'HMS'}, {'ItemCode': 300384.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': 'HMS', 'BW08': ' '}, {'ItemCode': 300393.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': 'HMS', 'BW08': ' '}, {'ItemCode': 300394.0, 'BW01': 'HMS', 'BW04': '', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 300395.0, 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300349.0, 'BW01': '', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 'C00001', 'BW01': '', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300374.0, 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300353.0, 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300347.0, 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300398.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': '', 'BW08': ''}, {'ItemCode': 'new ', 'BW01': '', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300417.0, 'BW01': '', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300433.0, 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300401.0, 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300440.0, 'BW01': '', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300439.0, 'BW01': '', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300449.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': 'HMS', 'BW08': ''}, {'ItemCode': 300451.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': 'HMS', 'BW08': ''}, {'ItemCode': 300452.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': 'HMS', 'BW08': ''}, {'ItemCode': 300453.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': 'HMS', 'BW08': ''}, {'ItemCode': 300454.0, 'BW01': 'HMS', 'BW04': 'HMS', 'BW07': 'HMS', 'BW10': 'HMS', 'BW08': ''}, {'ItemCode': '300318-F', 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 200174.0, 'BW01': '', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300464.0, 'BW01': '', 'BW04': 'HMS', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 200411.0, 'BW01': '', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300488.0, 'BW01': 'HMS', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300155.0, 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300166.0, 'BW01': 'RRP', 'BW04': 'RRP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 300167.0, 'BW01': 'RRP', 'BW04': 'RRP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 300168.0, 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300169.0, 'BW01': 'RRP', 'BW04': 'RRP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 300162.0, 'BW01': 'RRP', 'BW04': 'RRP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 300180.0, 'BW01': 'RRP', 'BW04': 'RRP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 300181.0, 'BW01': 'RRP', 'BW04': 'RRP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 300187.0, 'BW01': 'RRP', 'BW04': 'RRP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 300188.0, 'BW01': '', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': '300191 - GLR', 'BW01': 'RRP', 'BW04': 'RRP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 300213.0, 'BW01': 'RRP', 'BW04': 'RRP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 300214.0, 'BW01': 'RRP', 'BW04': 'RRP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 300216.0, 'BW01': 'RRP', 'BW04': 'RRP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 300221.0, 'BW01': 'RRP', 'BW04': 'RRP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 300226.0, 'BW01': 'RRP', 'BW04': 'RRP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 300236.0, 'BW01': 'RRP', 'BW04': 'RRP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 300309.0, 'BW01': '', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': 'RRP'}, {'ItemCode': 300314.0, 'BW01': '', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300317.0, 'BW01': 'RRP', 'BW04': 'RRP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 300341.0, 'BW01': '', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': '300188_R', 'BW01': 'RRP', 'BW04': 'RRP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': '300191 - ICS', 'BW01': 'RRP', 'BW04': 'RRP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': '300191 - ILR', 'BW01': 'RRP', 'BW04': 'RRP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 300218.0, 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300362.0, 'BW01': 'RRP', 'BW04': 'RRP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 300346.0, 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': '300191 - MH', 'BW01': 'RRP', 'BW04': 'RRP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': '300191 - ATL', 'BW01': 'RRP', 'BW04': 'RRP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 300191.0, 'BW01': 'RRP', 'BW04': 'RRP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 300269.0, 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': '300191 - PLR', 'BW01': 'RRP', 'BW04': 'RRP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 400933.0, 'BW01': 'RRP', 'BW04': 'RRP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401362.0, 'BW01': 'RRP', 'BW04': 'RRP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401363.0, 'BW01': 'RRP', 'BW04': 'RRP', 'BW07': 'RRP', 'BW10': 'RRP', 'BW08': 'RRP'}, {'ItemCode': 300397.0, 'BW01': '', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300361.0, 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 200358.0, 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 600022.0, 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 400435.0, 'BW01': 'RRP', 'BW04': 'RRP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 300392.0, 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': '300392 bold', 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': '300191 - GLRC', 'BW01': 'RRP', 'BW04': 'RRP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': '300191 - UCS', 'BW01': 'RRP', 'BW04': 'RRP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 200172.0, 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': '300168 - BOLD', 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 'STRACH ROLL', 'BW01': '', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300434.0, 'BW01': '', 'BW04': 'RRP', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300233.0, 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': '300191 - ILRC', 'BW01': 'RRP', 'BW04': 'RRP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 300462.0, 'BW01': 'RRP', 'BW04': 'RRP', 'BW07': 'RRP', 'BW10': 'RRP', 'BW08': ''}, {'ItemCode': 300402.0, 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': '200172C', 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': '200172B', 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 300510.0, 'BW01': 'RRP', 'BW04': 'RRP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 300511.0, 'BW01': 'RRP', 'BW04': 'RRP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': '200172_S', 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX013', 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX014', 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX021', 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX022', 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX026', 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX028', 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX036', 'BW01': '', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': 'RRP'}, {'ItemCode': 'BOX038', 'BW01': '', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX041', 'BW01': '', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX051', 'BW01': 'RRP', 'BW04': '', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX053', 'BW01': '', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX056', 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX074', 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX075', 'BW01': '', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX076', 'BW01': '', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX077', 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX078', 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': 'RRP', 'BW08': ''}, {'ItemCode': 'BOX079', 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': 'RRP', 'BW08': ''}, {'ItemCode': 'BOX082', 'BW01': 'RRP', 'BW04': '', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX085', 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': 'RRP', 'BW08': ''}, {'ItemCode': 'BOX088', 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX092', 'BW01': '', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': 'RRP'}, {'ItemCode': 'BOX095', 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX096', 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX100', 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX101', 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX102', 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX104', 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX105', 'BW01': '', 'BW04': '', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX108', 'BW01': '', 'BW04': '', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX109', 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX111', 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX112', 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 'Box113', 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX118', 'BW01': '', 'BW04': '', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX119', 'BW01': '', 'BW04': '', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX120', 'BW01': '', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX122', 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX123', 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX124', 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX126', 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX127', 'BW01': '', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX128', 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX129', 'BW01': '', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': 'RRP', 'BW08': ''}, {'ItemCode': 'BOX130', 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX131', 'BW01': '', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': 'RRP', 'BW08': ''}, {'ItemCode': 'BOX133', 'BW01': '', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': 'RRP', 'BW08': ''}, {'ItemCode': 'BOX137', 'BW01': '', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX138', 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX140', 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX143', 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX146', 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX147', 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX148', 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX149', 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX150', 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': 'RRP', 'BW08': ''}, {'ItemCode': 'BOX151', 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX152', 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX153', 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX154', 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX155', 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 'BOX156', 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 401452.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401531.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401809.0, 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 401838.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401830.0, 'BW01': '', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401881.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401894.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 402008.0, 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 400834.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 400842.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401177.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401377.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401463.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401516.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401528.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401284.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401533.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401553.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401202.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401298.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401329.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401169.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401171.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401530.0, 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 401190.0, 'BW01': '', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': 'RRP'}, {'ItemCode': 401191.0, 'BW01': '', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': 'RRP'}, {'ItemCode': 401278.0, 'BW01': '', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': 'RRP'}, {'ItemCode': 401359.0, 'BW01': '', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': 'RRP'}, {'ItemCode': 401409.0, 'BW01': '', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': 'RRP'}, {'ItemCode': 401791.0, 'BW01': '', 'BW04': '', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401587.0, 'BW01': '', 'BW04': '', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401725.0, 'BW01': 'RRP', 'BW04': '', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401707.0, 'BW01': 'RRP', 'BW04': '', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'ROB 401564', 'BW01': '', 'BW04': 'SBP', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 'ROB 401492', 'BW01': '', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'ROB 401493', 'BW01': '', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'ROB 401465', 'BW01': '', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401851.0, 'BW01': '', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401612.0, 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 402004.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 402005.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 402001.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 400929.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 402002.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401419.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 402003.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 400928.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401733.0, 'BW01': '', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401662.0, 'BW01': '', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401995.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401996.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401997.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 401998.0, 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 401999.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 402000.0, 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 401989.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401990.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401991.0, 'BW01': '', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401992.0, 'BW01': '', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401993.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401994.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401988.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401987.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401218.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401223.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401981.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401982.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401983.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401984.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401985.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401986.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401681.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401246.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401977.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401978.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401979.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401980.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401641.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401923.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401942.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 402049.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401669.0, 'BW01': 'RRP', 'BW04': '', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401702.0, 'BW01': 'RRP', 'BW04': '', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401572.0, 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 401647.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401646.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401758.0, 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 401808.0, 'BW01': '', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': 'RRP'}, {'ItemCode': 401811.0, 'BW01': '', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': 'RRP'}, {'ItemCode': 'R 401564', 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 'R 401492', 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 'R 401493', 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 'R 401465', 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 'R 401851', 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 'CARTON 25*240 CORN CHIPS\xa0', 'BW01': '', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': 'RRP'}, {'ItemCode': 'R 401624', 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'R 401654', 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'CARTON 50*120 CORN CHIPS\xa0', 'BW01': '', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': 'RRP'}, {'ItemCode': 401853.0, 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 401849.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401836.0, 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 401837.0, 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 401871.0, 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 401855.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401856.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401860.0, 'BW01': '', 'BW04': '', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401859.0, 'BW01': '', 'BW04': '', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401865.0, 'BW01': '', 'BW04': '', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401882.0, 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 401883.0, 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 401884.0, 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 401895.0, 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 401961.0, 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 401901.0, 'BW01': '', 'BW04': '', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401897.0, 'BW01': '', 'BW04': '', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401925.0, 'BW01': '', 'BW04': '', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401928.0, 'BW01': '', 'BW04': '', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401900.0, 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 401936.0, 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 401911.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401919.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401968.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401905.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401921.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401930.0, 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 401939.0, 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 401940.0, 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 'M401854', 'BW01': '', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401957.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'M401862', 'BW01': '', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'M401521', 'BW01': '', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401969.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'R401915', 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 'M401898', 'BW01': '', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'M401915', 'BW01': '', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401685.0, 'BW01': '', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'R401862', 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 'R401521', 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 'R401854', 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 'M401855', 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'M401856', 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401974.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401975.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'R401662', 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 'R401898', 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 'RCARTON 25*240 TIKHA GATHIYA', 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 'RCARTON 25*240 CHAMPAKALI GATHIYA\xa0', 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 'R401451', 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 401970.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401958.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'CARTON 50*144 TIKHA GATHIYA', 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401971.0, 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401972.0, 'BW01': 'RRP', 'BW04': '', 'BW07': '', 'BW10': '', 'BW08': ''}, {'ItemCode': 'R401913', 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 'RCARTON 50*120 CHAMPAKALI GATHIYA', 'BW01': 'RRP', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}, {'ItemCode': 401451.0, 'BW01': '', 'BW04': 'SBP', 'BW07': 'RRP', 'BW10': '', 'BW08': ''}]
        prod_obj = self.env['product.template'].sudo()
        user_obj = self.env['res.users'].sudo()
        company_obj = self.env['res.company'].sudo()
        item_owner_obj = self.env['product.owner.info'].sudo()
        one_plant = company_obj.search([('code', '=', 'BW01')])
        two_plant = company_obj.search([('code', '=', 'BW04')])
        three_plant = company_obj.search([('code', '=', 'BW07')])
        four_plant = company_obj.search([('code', '=', 'BW10')])
        five_plant = company_obj.search([('code', '=', 'BW08')])
        for raw in product_owner:
            prod = raw.get('ItemCode', '')
            if type(prod) == float:
                prod = str(int(prod))
            product = False
            product = prod_obj.search([('default_code', '=', prod)])
            one = raw.get('BW01', '')
            two = raw.get('BW04', '')
            three = raw.get('BW07', '')
            four = raw.get('BW10', '')
            five = raw.get('BW08', '')
            products = prod_obj.search([('default_code', '=', prod)])
            if products:
                if len(products) > 1:
                    pass
                for product in products:
                    if one:
                        user = False
                        user = user_obj.search([('name', '=', one)])
                        if user:
                            item_owner_obj.create({'product_tmpl_id': product.id,
                                                   'user_id': user.id,
                                                   'plant_ids': one_plant.ids})

                    if two:
                        user = False
                        user = user_obj.search([('name', '=', one)])
                        if user:
                            item_owner_obj.create({'product_tmpl_id': product.id,
                                                   'user_id': user.id,
                                                   'plant_ids': two_plant.ids})

                    if three:
                        user = False
                        user = user_obj.search([('name', '=', one)])
                        if user:
                            item_owner_obj.create({'product_tmpl_id': product.id,
                                                   'user_id': user.id,
                                                   'plant_ids': three_plant.ids})

                    if four:
                        user = False
                        user = user_obj.search([('name', '=', one)])
                        if user:
                            item_owner_obj.create({'product_tmpl_id': product.id,
                                                   'user_id': user.id,
                                                   'plant_ids': four_plant.ids})

                    if five:
                        user = False
                        user = user_obj.search([('name', '=', one)])
                        if user:
                            item_owner_obj.create({'product_tmpl_id': product.id,
                                                   'user_id': user.id,
                                                   'plant_ids': five_plant.ids})
        return True

    def set_product_requestor(self):
        requestor_data = [
            {'sep_code': 300156.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300157.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300158.0, 'req_requestor': 'RM01, RM04, RM07, RM10'}, {'sep_code': 300159.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300160.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300161.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300163.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300164.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300165.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300170.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300171.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300172.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300173.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300174.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300175.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300176.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300177.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300178.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300179.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300182.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300183.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300184.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300185.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300186.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300189.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300190.0, 'req_requestor': 'RM01, RM04, RM07, RM10'}, {'sep_code': 300193.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300194.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300195.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300196.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300197.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300198.0, 'req_requestor': ''}, {'sep_code': 300199.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300200.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300201.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300202.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300203.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300204.0, 'req_requestor': 'RM01'}, {'sep_code': 300205.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300206.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300207.0, 'req_requestor': ''}, {'sep_code': 300208.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300209.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300212.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300215.0, 'req_requestor': ''}, {'sep_code': 300219.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300220.0, 'req_requestor': 'RM01, RM07'}, {'sep_code': 300222.0, 'req_requestor': 'RM01, RM07'}, {'sep_code': 300225.0, 'req_requestor': 'RM01, RM04, RM07, RM10'}, {'sep_code': 300228.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300230.0, 'req_requestor': ''}, {'sep_code': 300232.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300235.0, 'req_requestor': 'TE'}, {'sep_code': 300237.0, 'req_requestor': 'RM01, RM04, RM07, RM10'}, {'sep_code': 300238.0, 'req_requestor': ''}, {'sep_code': 300240.0, 'req_requestor': 'TE, RM04, RM07'}, {'sep_code': 300241.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300245.0, 'req_requestor': 'RM04, RM07'}, {'sep_code': 300249.0, 'req_requestor': 'RM01, RM07'}, {'sep_code': 300251.0, 'req_requestor': 'RM01, RM04, RM07, RM10'}, {'sep_code': 300252.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300253.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300254.0, 'req_requestor': 'RM01, RM04, RM07, RM10'}, {'sep_code': 300255.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300257.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300258.0, 'req_requestor': 'RM01, RM04, RM07, RM10'}, {'sep_code': 300259.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300261.0, 'req_requestor': ''}, {'sep_code': 300266.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300267.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300272.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300273.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300279.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300281.0, 'req_requestor': 'RM01, RM04, RM07, RM10'}, {'sep_code': 300282.0, 'req_requestor': 'MK'}, {'sep_code': 300283.0, 'req_requestor': 'MK'}, {'sep_code': 300289.0, 'req_requestor': ''}, {'sep_code': 300290.0, 'req_requestor': 'MK'}, {'sep_code': 300292.0, 'req_requestor': 'MK'}, {'sep_code': 300293.0, 'req_requestor': ''}, {'sep_code': 300299.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300300.0, 'req_requestor': 'MK'}, {'sep_code': 300306.0, 'req_requestor': 'MK'}, {'sep_code': 300307.0, 'req_requestor': 'RM10'}, {'sep_code': 300308.0, 'req_requestor': 'TE'}, {'sep_code': 300310.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300313.0, 'req_requestor': 'TE'}, {'sep_code': 300315.0, 'req_requestor': 'RM01, RM04, RM07, RM10'}, {'sep_code': 300316.0, 'req_requestor': 'RM01, RM07'}, {'sep_code': 300319.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300320.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300321.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300322.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300323.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300324.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300325.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300327.0, 'req_requestor': 'TE'}, {'sep_code': 300328.0, 'req_requestor': 'TE'}, {'sep_code': 300329.0, 'req_requestor': 'TE'}, {'sep_code': 300331.0, 'req_requestor': ''}, {'sep_code': 300332.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300333.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300334.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300338.0, 'req_requestor': ''}, {'sep_code': 300339.0, 'req_requestor': ''}, {'sep_code': 300340.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300342.0, 'req_requestor': 'MK'}, {'sep_code': 300343.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300344.0, 'req_requestor': ''}, {'sep_code': 300223.0, 'req_requestor': ''}, {'sep_code': 300291.0, 'req_requestor': ''}, {'sep_code': 600000.0, 'req_requestor': ''}, {'sep_code': 300355.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300359.0, 'req_requestor': 'VF'}, {'sep_code': 300360.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300364.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300365.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300376.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300377.0, 'req_requestor': ''}, {'sep_code': 300378.0, 'req_requestor': 'RM01, RM04, RM07, RM10'}, {'sep_code': 300384.0, 'req_requestor': 'RM01, RM04, RM07, RM10'}, {'sep_code': 300393.0, 'req_requestor': ''}, {'sep_code': 300394.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300395.0, 'req_requestor': ''}, {'sep_code': 300349.0, 'req_requestor': 'WF'}, {'sep_code': 'C00001', 'req_requestor': ''}, {'sep_code': 300374.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300353.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300347.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300398.0, 'req_requestor': 'HMS, RM04, RM07'}, {'sep_code': 'new ', 'req_requestor': ''}, {'sep_code': 300417.0, 'req_requestor': ''}, {'sep_code': 300433.0, 'req_requestor': 'MK'}, {'sep_code': 300401.0, 'req_requestor': 'VF'}, {'sep_code': 300440.0, 'req_requestor': ''}, {'sep_code': 300439.0, 'req_requestor': ''}, {'sep_code': 300449.0, 'req_requestor': 'HMS, RM04, RM07, RM10'}, {'sep_code': 300451.0, 'req_requestor': 'HMS, RM04, RM07, RM10'}, {'sep_code': 300452.0, 'req_requestor': 'HMS, RM04, RM07, RM10'}, {'sep_code': 300453.0, 'req_requestor': 'HMS, RM04, RM07, RM10'}, {'sep_code': 300454.0, 'req_requestor': 'HMS, RM04, RM07, RM10'}, {'sep_code': '300318-F', 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 200174.0, 'req_requestor': ''}, {'sep_code': 300464.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 200411.0, 'req_requestor': ''}, {'sep_code': 300488.0, 'req_requestor': 'MK'}, {'sep_code': 300155.0, 'req_requestor': 'RM01'}, {'sep_code': 300166.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300167.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300168.0, 'req_requestor': 'RM01'}, {'sep_code': 300169.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300162.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300180.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300181.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300187.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300188.0, 'req_requestor': ''}, {'sep_code': '300191 - GLR', 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300213.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300214.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300216.0, 'req_requestor': 'RM01, RM04, RM07, RM10, WF'}, {'sep_code': 300221.0, 'req_requestor': 'RM01, RM07'}, {'sep_code': 300226.0, 'req_requestor': 'RM01'}, {'sep_code': 300236.0, 'req_requestor': 'TE, RM04, RM07'}, {'sep_code': 300309.0, 'req_requestor': 'WF'}, {'sep_code': 300314.0, 'req_requestor': ''}, {'sep_code': 300317.0, 'req_requestor': 'DF'}, {'sep_code': 300341.0, 'req_requestor': ''}, {'sep_code': '300188_R', 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': '300191 - ICS', 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': '300191 - ILR', 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300218.0, 'req_requestor': 'RM01'}, {'sep_code': 300362.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300346.0, 'req_requestor': 'TE'}, {'sep_code': '300191 - MH', 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': '300191 - ATL', 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300191.0, 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300269.0, 'req_requestor': 'RM01'}, {'sep_code': '300191 - PLR', 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 400933.0, 'req_requestor': 'PM01, RM04, RM07, RM10'}, {'sep_code': 401362.0, 'req_requestor': 'PM01, RM04, RM07, RM10'}, {'sep_code': 401363.0, 'req_requestor': 'PM01, RM04, RM07, RM10, WF'}, {'sep_code': 300397.0, 'req_requestor': ''}, {'sep_code': 300361.0, 'req_requestor': 'TE'}, {'sep_code': 200358.0, 'req_requestor': 'TE'}, {'sep_code': 600022.0, 'req_requestor': 'TE'}, {'sep_code': 400435.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 300392.0, 'req_requestor': 'VF'}, {'sep_code': '300392 bold', 'req_requestor': 'VF'}, {'sep_code': '300191 - GLRC', 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': '300191 - UCS', 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 200172.0, 'req_requestor': 'RM01'}, {'sep_code': '300168 - BOLD', 'req_requestor': 'RM01'}, {'sep_code': 'STRACH ROLL', 'req_requestor': ''}, {'sep_code': 300434.0, 'req_requestor': 'RM04'}, {'sep_code': 300233.0, 'req_requestor': 'AJI'}, {'sep_code': '300191 - ILRC', 'req_requestor': 'RM01, RM04, RM07'}, {'sep_code': 300462.0, 'req_requestor': 'RM01, RM04, RM07, RM10'}, {'sep_code': 300402.0, 'req_requestor': 'RM01'}, {'sep_code': '200172C', 'req_requestor': 'VF'}, {'sep_code': '200172B', 'req_requestor': 'RM01'}, {'sep_code': 300510.0, 'req_requestor': 'RM01, RM04, RM07, RM10'}, {'sep_code': 300511.0, 'req_requestor': 'RM01, RM04, RM07, RM10'}, {'sep_code': '200172_S', 'req_requestor': 'RM01'}, {'sep_code': 'BOX013', 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 'BOX014', 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 'BOX021', 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 'BOX022', 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 'BOX026', 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 'BOX028', 'req_requestor': 'PM01'}, {'sep_code': 'BOX036', 'req_requestor': ''}, {'sep_code': 'BOX038', 'req_requestor': 'RM04, RM07'}, {'sep_code': 'BOX041', 'req_requestor': 'RM04, RM07'}, {'sep_code': 'BOX051', 'req_requestor': 'PM01, RM07'}, {'sep_code': 'BOX053', 'req_requestor': 'RM04, RM07'}, {'sep_code': 'BOX056', 'req_requestor': 'PM01'}, {'sep_code': 'BOX074', 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 'BOX075', 'req_requestor': 'RM04, RM07'}, {'sep_code': 'BOX076', 'req_requestor': 'RM04, RM07'}, {'sep_code': 'BOX077', 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 'BOX078', 'req_requestor': 'PM01, RM04, RM07, RM10'}, {'sep_code': 'BOX079', 'req_requestor': 'PM01, RM04, RM07, RM10'}, {'sep_code': 'BOX082', 'req_requestor': 'PM01, RM07'}, {'sep_code': 'BOX085', 'req_requestor': 'PM01, RM04, RM07, RM10'}, {'sep_code': 'BOX088', 'req_requestor': 'PM01'}, {'sep_code': 'BOX092', 'req_requestor': ''}, {'sep_code': 'BOX095', 'req_requestor': 'PM01'}, {'sep_code': 'BOX096', 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 'BOX100', 'req_requestor': 'PM01'}, {'sep_code': 'BOX101', 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 'BOX102', 'req_requestor': ''}, {'sep_code': 'BOX104', 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 'BOX105', 'req_requestor': 'RM07'}, {'sep_code': 'BOX108', 'req_requestor': 'RM07'}, {'sep_code': 'BOX109', 'req_requestor': 'PM01'}, {'sep_code': 'BOX111', 'req_requestor': 'PM01'}, {'sep_code': 'BOX112', 'req_requestor': 'PM01'}, {'sep_code': 'Box113', 'req_requestor': 'PM01'}, {'sep_code': 'BOX118', 'req_requestor': 'RM07'}, {'sep_code': 'BOX119', 'req_requestor': 'RM07'}, {'sep_code': 'BOX120', 'req_requestor': 'RM04, RM07'}, {'sep_code': 'BOX122', 'req_requestor': 'PM01'}, {'sep_code': 'BOX123', 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 'BOX124', 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 'BOX126', 'req_requestor': 'PM01'}, {'sep_code': 'BOX127', 'req_requestor': 'RM04, RM07'}, {'sep_code': 'BOX128', 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 'BOX129', 'req_requestor': 'RM04, RM07, RM10'}, {'sep_code': 'BOX130', 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 'BOX131', 'req_requestor': 'RM04, RM07, RM10'}, {'sep_code': 'BOX133', 'req_requestor': 'RM04, RM07, RM10'}, {'sep_code': 'BOX137', 'req_requestor': 'RM04, RM07'}, {'sep_code': 'BOX138', 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 'BOX140', 'req_requestor': 'PM01'}, {'sep_code': 'BOX143', 'req_requestor': 'PM01'}, {'sep_code': 'BOX146', 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 'BOX147', 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 'BOX148', 'req_requestor': 'PM01'}, {'sep_code': 'BOX149', 'req_requestor': 'PM01'}, {'sep_code': 'BOX150', 'req_requestor': 'PM01, RM10'}, {'sep_code': 'BOX151', 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 'BOX152', 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 'BOX153', 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 'BOX154', 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 'BOX155', 'req_requestor': 'PM01'}, {'sep_code': 'BOX156', 'req_requestor': 'PM01'}, {'sep_code': 401452.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401531.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401809.0, 'req_requestor': 'PM01'}, {'sep_code': 401838.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401830.0, 'req_requestor': 'RM04, RM07'}, {'sep_code': 401881.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401894.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 402008.0, 'req_requestor': 'TE'}, {'sep_code': 400834.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 400842.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401177.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401377.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401463.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401516.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401528.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401284.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401533.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401553.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401202.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401298.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401329.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401169.0, 'req_requestor': 'TE, RM04, RM07'}, {'sep_code': 401171.0, 'req_requestor': 'TE, RM04, RM07'}, {'sep_code': 401530.0, 'req_requestor': 'TE'}, {'sep_code': 401190.0, 'req_requestor': 'WF'}, {'sep_code': 401191.0, 'req_requestor': 'WF'}, {'sep_code': 401278.0, 'req_requestor': 'WF'}, {'sep_code': 401359.0, 'req_requestor': 'WF'}, {'sep_code': 401409.0, 'req_requestor': 'WF'}, {'sep_code': 401791.0, 'req_requestor': 'RM07'}, {'sep_code': 401587.0, 'req_requestor': 'RM07'}, {'sep_code': 401725.0, 'req_requestor': 'PM01, RM07'}, {'sep_code': 401707.0, 'req_requestor': 'PM01, RM07'}, {'sep_code': 'ROB 401564', 'req_requestor': 'RM04'}, {'sep_code': 'ROB 401492', 'req_requestor': 'RM04, RM07'}, {'sep_code': 'ROB 401493', 'req_requestor': 'RM04, RM07'}, {'sep_code': 'ROB 401465', 'req_requestor': 'RM04, RM07'}, {'sep_code': 401851.0, 'req_requestor': 'RM04, RM07'}, {'sep_code': 401612.0, 'req_requestor': 'MK'}, {'sep_code': 402004.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 402005.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 402001.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 400929.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 402002.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401419.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 402003.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 400928.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401733.0, 'req_requestor': 'RM04, RM07'}, {'sep_code': 401662.0, 'req_requestor': 'RM04, RM07'}, {'sep_code': 401995.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401996.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401997.0, 'req_requestor': 'PM01, RM04'}, {'sep_code': 401998.0, 'req_requestor': 'PM01'}, {'sep_code': 401999.0, 'req_requestor': 'PM01, RM04'}, {'sep_code': 402000.0, 'req_requestor': 'PM01'}, {'sep_code': 401989.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401990.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401991.0, 'req_requestor': 'RM04, RM07'}, {'sep_code': 401992.0, 'req_requestor': 'RM04, RM07'}, {'sep_code': 401993.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401994.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401988.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401987.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401218.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401223.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401981.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401982.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401983.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401984.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401985.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401986.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401681.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401246.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401977.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401978.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401979.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401980.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401641.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401923.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401942.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 402049.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401669.0, 'req_requestor': 'PM01, RM07'}, {'sep_code': 401702.0, 'req_requestor': 'PM01, RM07'}, {'sep_code': 401572.0, 'req_requestor': 'PM01'}, {'sep_code': 401647.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401646.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401758.0, 'req_requestor': 'MK'}, {'sep_code': 401808.0, 'req_requestor': 'WF'}, {'sep_code': 401811.0, 'req_requestor': 'WF'}, {'sep_code': 'R 401564', 'req_requestor': 'PM01'}, {'sep_code': 'R 401492', 'req_requestor': 'PM01'}, {'sep_code': 'R 401493', 'req_requestor': 'PM01'}, {'sep_code': 'R 401465', 'req_requestor': 'PM01'}, {'sep_code': 'R 401851', 'req_requestor': 'PM01'}, {'sep_code': 'CARTON 25*240 CORN CHIPS\xa0', 'req_requestor': 'WF'}, {'sep_code': 'R 401624', 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 'R 401654', 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 'CARTON 50*120 CORN CHIPS\xa0', 'req_requestor': 'WF'}, {'sep_code': 401853.0, 'req_requestor': 'DF'}, {'sep_code': 401849.0, 'req_requestor': 'TE, RM04, RM07'}, {'sep_code': 401836.0, 'req_requestor': 'AJI'}, {'sep_code': 401837.0, 'req_requestor': 'AJI'}, {'sep_code': 401871.0, 'req_requestor': 'AJI'}, {'sep_code': 401855.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401856.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401860.0, 'req_requestor': 'RM07'}, {'sep_code': 401859.0, 'req_requestor': 'RM07'}, {'sep_code': 401865.0, 'req_requestor': 'RM07'}, {'sep_code': 401882.0, 'req_requestor': 'VF'}, {'sep_code': 401883.0, 'req_requestor': 'DF'}, {'sep_code': 401884.0, 'req_requestor': 'DF'}, {'sep_code': 401895.0, 'req_requestor': 'MK'}, {'sep_code': 401961.0, 'req_requestor': 'MK'}, {'sep_code': 401901.0, 'req_requestor': 'RM07'}, {'sep_code': 401897.0, 'req_requestor': 'RM07'}, {'sep_code': 401925.0, 'req_requestor': 'RM07'}, {'sep_code': 401928.0, 'req_requestor': 'RM07'}, {'sep_code': 401900.0, 'req_requestor': 'TE'}, {'sep_code': 401936.0, 'req_requestor': 'TE'}, {'sep_code': 401911.0, 'req_requestor': 'TE, RM04, RM07'}, {'sep_code': 401919.0, 'req_requestor': 'TE, RM04, RM07'}, {'sep_code': 401968.0, 'req_requestor': 'TE, RM04, RM07'}, {'sep_code': 401905.0, 'req_requestor': 'TE, RM04, RM07'}, {'sep_code': 401921.0, 'req_requestor': 'TE, RM04, RM07'}, {'sep_code': 401930.0, 'req_requestor': 'MK'}, {'sep_code': 401939.0, 'req_requestor': 'MK'}, {'sep_code': 401940.0, 'req_requestor': 'MK'}, {'sep_code': 'M401854', 'req_requestor': 'RM04, RM07'}, {'sep_code': 401957.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 'M401862', 'req_requestor': 'RM04, RM07'}, {'sep_code': 'M401521', 'req_requestor': 'RM04, RM07'}, {'sep_code': 401969.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 'R401915', 'req_requestor': 'PM01'}, {'sep_code': 'M401898', 'req_requestor': 'RM04, RM07'}, {'sep_code': 'M401915', 'req_requestor': 'RM04, RM07'}, {'sep_code': 401685.0, 'req_requestor': 'RM04, RM07'}, {'sep_code': 'R401862', 'req_requestor': 'PM01'}, {'sep_code': 'R401521', 'req_requestor': 'PM01'}, {'sep_code': 'R401854', 'req_requestor': 'PM01'}, {'sep_code': 'M401855', 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 'M401856', 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401974.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401975.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 'R401662', 'req_requestor': 'PM01'}, {'sep_code': 'R401898', 'req_requestor': 'PM01'}, {'sep_code': 'RCARTON 25*240 TIKHA GATHIYA', 'req_requestor': 'PM01'}, {'sep_code': 'RCARTON 25*240 CHAMPAKALI GATHIYA\xa0', 'req_requestor': 'PM01'}, {'sep_code': 'R401451', 'req_requestor': 'PM01'}, {'sep_code': 401970.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401958.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 'CARTON 50*144 TIKHA GATHIYA', 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401971.0, 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401972.0, 'req_requestor': 'PM01'}, {'sep_code': 'R401913', 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 'RCARTON 50*120 CHAMPAKALI GATHIYA', 'req_requestor': 'PM01, RM04, RM07'}, {'sep_code': 401451.0, 'req_requestor': 'RM04, RM07'}]

        product_tmpl_obj = self.env['product.template'].sudo()

        for data in requestor_data:
            product_code = data.get('sep_code')
            if type(product_code) == float:
                product_code = str(int(product_code))
            product = product_tmpl_obj.search([('default_code', '=', product_code)], limit=1)
            if product:
                user_data = data.get('req_requestor')
                if user_data:
                    req_ids = []
                    for user_name in user_data.split(', '):
                        user = self.env['res.users'].search([('name', '=', user_name)], limit=1)
                        if user:
                            req_ids.append(user.id)
                    print(product.name)
                    print(req_ids)
                    product.write({'requisition_requester_ids': [(6, 0, req_ids)]})
        return True

    def set_parent_prod_in_prod(self,attachment_id):
        file_data = self.read_file(attachment_id)
        parent_prod_data = file_data.get('data')
        parent_prod_data = [{'ItemCode': data.get('ItemCode'), 'ParentItemCode': data.get('ParentItemCode'),'Itemname':data.get('Itemname')} for data in parent_prod_data]
        prod_obj = self.env['product.template'].sudo()
        not_set_parent = []
        for raw in parent_prod_data:
            prod = raw.get('ItemCode', '')
            if type(prod) == float:
                prod = str(int(prod))
            product = False
            product = prod_obj.search([('default_code', '=', prod)],limit=1)
            if product and raw.get('ParentItemCode') and raw.get('ParentItemCode') != 'NULL':
                parent_prod = raw.get('ParentItemCode', '')
                if type(parent_prod) == float:
                    parent_prod = str(int(parent_prod))
                parent_product = False
                parent_product = prod_obj.search([('default_code', '=', parent_prod)],limit=1)
                if parent_product:
                    product.parent_id = parent_product.id
                else:
                    not_set_parent.append(raw)
            else:
                not_set_parent.append(raw)
        return  not_set_parent

    def set_archive_prod_in_prod(self):
        archive_prod_data = [
            "300198","300199","300201","300207","300215","300230","300238","300261","300289","300293","300331","300338","300339","300344","300223","300291","600000","300377","300393","300395","C00001","new ","300417","300440","300439","200174","200411","300188","300314","300341","300397","STRACH ROLL","RB0002","401613","401479","401892","400647","401914","401918","401764","400632","400957"]
        prod_obj = self.env['product.template'].sudo()
        for prod in archive_prod_data:
            if type(prod) == float:
                prod = str(int(prod))
            product = False
            product = prod_obj.search([('default_code', '=', prod)],limit=1)
            if product:
                product.active = False
                product.archive_reason = "Default Archive"
        return  True

    def check_unique_specification(self,attachment_id):
        file_data = self.read_file(attachment_id)
        spec_data = file_data.get('data')
        specification_dict = {}
        duplicate_specification = []
        for spec in spec_data:
            if specification_dict and specification_dict.get(spec.get('New Item Code')):
                value = specification_dict.get(spec.get('New Item Code'))
                if spec.get('SpecName') in value:
                    duplicate_specification.append(spec)
                    continue
                else:
                    specification_dict.get(spec.get('New Item Code')).append(spec.get('SpecName'))
            else:
                specification_dict.update({spec['New Item Code']:[spec['SpecName']]})
        return duplicate_specification
