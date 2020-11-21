from odoo import fields,api,models,_

class AccountMoveInherit(models.Model):
    _inherit = 'account.move'

    # trading_order = fields.Boolean('Trading')
    # service_order = fields.Boolean('Service')
    so_type = fields.Selection([
        ('trading', 'Trading'),
        ('service', 'Service')], string='Type')

    po_number_customer = fields.Char('P/O Number')

    project_ids = fields.Many2many('project.project', string='Project')

    @api.model
    def _move_autocomplete_invoice_lines_create(self, vals_list):
        ''' During the create of an account.move with only 'invoice_line_ids' set and not 'line_ids', this method is called
        to auto compute accounting lines of the invoice. In that case, accounts will be retrieved and taxes, cash rounding
        and payment terms will be computed. At the end, the values will contains all accounting lines in 'line_ids'
        and the moves should be balanced.

        :param vals_list:   The list of values passed to the 'create' method.
        :return:            Modified list of values.
        '''
        new_vals_list = []
        for vals in vals_list:
            if not vals.get('invoice_line_ids'):
                new_vals_list.append(vals)
                continue
            if vals.get('line_ids'):
                vals.pop('invoice_line_ids', None)
                new_vals_list.append(vals)
                continue
            if not vals.get('move_type') and not self._context.get('default_move_type'):
                vals.pop('invoice_line_ids', None)
                new_vals_list.append(vals)
                continue
            vals['move_type'] = vals.get('move_type', self._context.get('default_move_type', 'entry'))
            if not vals['move_type'] in self.get_invoice_types(include_receipts=True):
                new_vals_list.append(vals)
                continue
            if vals.get('so_type') == 'service':
                cust_line_ids = vals.pop('invoice_line_ids')
                cust_vals = []
                for line in cust_line_ids:
                    print(line)
                    tup_line = line[2]
                    if tup_line.get('display_type') == 'line_section':
                        product_name = tup_line.get('name').split("  [", 1)[0]
                        split_wrd = tup_line.get('name').split("Subtotal: ", 1)
                        split_wrd1 = split_wrd[1]
                        split_wrd2 = split_wrd1.split("]", 1)
                        split_wrd3 = split_wrd2[0]
                        price_unit = float(split_wrd3)
                        product_temp_id = self.env['product.template'].sudo().search([('name', '=', product_name)])
                        product_id = self.env['product.product'].sudo().search(
                            [('product_tmpl_id', '=', product_temp_id.id)])
                        cust_vals.append((0, 0, {'display_type': False,
                                                 'sequence': tup_line.get('sequence'),
                                                 'name': tup_line.get('name'),
                                                 'product_id': product_id.id or False,
                                                 'product_uom_id': tup_line.get('product_uom_id'),
                                                 'quantity': 1,
                                                 'discount': tup_line.get('discount'),
                                                 'price_unit': price_unit or 0.0,
                                                 'tax_ids': tup_line.get('tax_ids'),
                                                 'analytic_account_id': tup_line.get('analytic_account_id'),
                                                 'analytic_tag_ids': tup_line.get('analytic_tag_ids'),
                                                 'sale_line_ids': tup_line.get('sale_line_ids'),
                                                 'account_id': tup_line.get('account_id')}))
                vals['line_ids'] = cust_vals
                print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>invoice_line_ids", vals['line_ids'])
            else:
                vals['line_ids'] = vals.pop('invoice_line_ids')
            if vals.get('invoice_date') and not vals.get('date'):
                vals['date'] = vals['invoice_date']

            ctx_vals = {'default_move_type': vals.get('move_type') or self._context.get('default_move_type')}
            if vals.get('currency_id'):
                ctx_vals['default_currency_id'] = vals['currency_id']
            if vals.get('journal_id'):
                ctx_vals['default_journal_id'] = vals['journal_id']
                # reorder the companies in the context so that the company of the journal
                # (which will be the company of the move) is the main one, ensuring all
                # property fields are read with the correct company
                journal_company = self.env['account.journal'].browse(vals['journal_id']).company_id
                allowed_companies = self._context.get('allowed_company_ids', journal_company.ids)
                reordered_companies = sorted(allowed_companies, key=lambda cid: cid != journal_company.id)
                ctx_vals['allowed_company_ids'] = reordered_companies
            self_ctx = self.with_context(**ctx_vals)
            new_vals = self_ctx._add_missing_default_values(vals)

            move = self_ctx.new(new_vals)
            new_vals_list.append(move._move_autocomplete_invoice_lines_values())

        return new_vals_list
