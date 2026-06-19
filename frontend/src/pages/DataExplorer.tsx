import { useState, useEffect } from 'react';
import { Table, Select, Button, Space, Card, message, Alert, Spin, Modal, Form, Input, Popconfirm } from 'antd';
import { PlayCircleOutlined, SaveOutlined, ClearOutlined, ExportOutlined, DeleteOutlined, EditOutlined, BranchesOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { DataSource } from '../types';
import { dataSourceApi, explorerApi } from '../api';
import SqlEditor from '../components/SqlEditor';

const { TextArea } = Input;
const { Option } = Select;

// Simple SQL formatter
function formatSql(sql: string): string {
  const keywords = ['SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'ORDER BY', 'GROUP BY', 'HAVING', 'LIMIT', 'JOIN', 'LEFT JOIN', 'RIGHT JOIN', 'INNER JOIN', 'ON', 'AS', 'DISTINCT', 'UNION'];
  let result = sql.trim();
  keywords.forEach((kw) => {
    const regex = new RegExp('\\b' + kw + '\\b', 'gi');
    result = result.replace(regex, '\n' + kw);
  });
  return result.replace(/^\n/, '').replace(/\n/g, '\n  ');
}

interface SavedTemplate {
  id: string;
  name: string;
  sql: string;
}

const DEFAULT_TEMPLATES: SavedTemplate[] = [
  { id: 'ap_suppliers', name: '供应商列表', sql: 'SELECT supplier_id, supplier_code, supplier_name, supplier_type, category, region, contact_person, contact_phone, created_date, status FROM ap_suppliers ORDER BY supplier_code' },
  { id: 'ar_customers', name: '客户列表', sql: 'SELECT customer_id, customer_code, customer_name, customer_type, industry, region, credit_limit, contact_person, contact_phone, created_date, status FROM ar_customers ORDER BY customer_code' },
  { id: 'gl_expenses', name: '费用数据', sql: 'SELECT expense_id, period, org_id, expense_type, amount, currency, created_date FROM gl_expenses ORDER BY period DESC, expense_id' },
  { id: 'gl_revenue', name: '收入数据', sql: 'SELECT revenue_id, period, org_id, revenue_type, amount, currency, created_date FROM gl_revenue ORDER BY period DESC, revenue_id' },
  { id: 'hr_departments', name: '部门列表', sql: 'SELECT dept_id, dept_code, dept_name, org_id, manager_id, created_date FROM hr_departments ORDER BY dept_code' },
  { id: 'hr_employees', name: '员工列表', sql: 'SELECT employee_id, employee_code, employee_name, dept_id, position, hire_date, salary, status FROM hr_employees ORDER BY employee_code' },
  { id: 'hr_organizations', name: '组织架构', sql: 'SELECT org_id, org_code, org_name, org_type, parent_org_id, region, created_date FROM hr_organizations ORDER BY org_code' },
  { id: 'inv_products', name: '产品列表', sql: 'SELECT product_id, product_code, product_name, category, unit, standard_cost, standard_price, stock_quantity, reorder_point, supplier_id, created_date, status FROM inv_products ORDER BY product_code' },
  { id: 'inv_transactions', name: '库存交易', sql: 'SELECT txn_id, txn_type, product_id, quantity, unit_cost, txn_date, reference_type, reference_id, warehouse_id, notes FROM inv_transactions ORDER BY txn_date DESC, txn_id' },
  { id: 'kpi_data', name: 'KPI数据', sql: 'SELECT kpi_id, period, org_id, kpi_name, kpi_value, target_value, unit, created_date FROM kpi_data ORDER BY period DESC, kpi_name' },
  { id: 'oe_order_lines', name: '订单明细', sql: 'SELECT line_id, order_id, product_id, quantity, unit_price, line_amount, shipped_quantity, invoiced_quantity FROM oe_order_lines ORDER BY order_id, line_id' },
  { id: 'oe_sales_orders', name: '销售订单', sql: 'SELECT order_id, order_number, customer_id, org_id, order_date, total_amount, paid_amount, order_status, payment_status, salesrep_id, created_date FROM oe_sales_orders ORDER BY order_date DESC, order_id' },
  { id: 'po_purchase_orders', name: '采购订单', sql: 'SELECT po_id, po_number, supplier_id, po_date, total_amount, received_amount, invoiced_amount, po_status, payment_status, created_by FROM po_purchase_orders ORDER BY po_date DESC, po_id' },
];

export default function DataExplorer() {
  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [selectedDs, setSelectedDs] = useState<number | null>(null);
  const [sql, setSql] = useState('SELECT * FROM gl_revenue LIMIT 20');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{
    success: boolean;
    columns: string[];
    rows: Record<string, unknown>[];
    row_count: number;
    error?: string;
  } | null>(null);
  const [templates, setTemplates] = useState<SavedTemplate[]>(DEFAULT_TEMPLATES);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);
  const [templateModalVisible, setTemplateModalVisible] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<SavedTemplate | null>(null);
  const [templateName, setTemplateName] = useState('');
  const [templateSql, setTemplateSql] = useState('');

  useEffect(() => {
    dataSourceApi.list().then((data) => {
      setDataSources(data);
      if (data.length > 0 && !selectedDs) {
        setSelectedDs(data[0].id);
      }
    }).catch(() => {
      message.error('加载数据源失败');
    });

    // Always use default templates, clear old localStorage
    localStorage.setItem('sqlTemplates', JSON.stringify(DEFAULT_TEMPLATES));
    setTemplates(DEFAULT_TEMPLATES);
  }, []);

  const handleExecute = async () => {
    if (!selectedDs) {
      message.warning('请先选择数据源');
      return;
    }
    if (!sql.trim()) {
      message.warning('请输入 SQL');
      return;
    }

    setLoading(true);
    setResult(null);
    try {
      const data = await explorerApi.query(selectedDs, sql);
      setResult(data);
      if (!data.success && data.error) {
        message.error(data.error);
      } else {
        message.success('查询成功，返回 ' + data.row_count + ' 条');
      }
    } catch {
      message.error('查询执行失败');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveTemplate = (t?: SavedTemplate) => {
    if (t) {
      setEditingTemplate(t);
      setTemplateName(t.name);
      setTemplateSql(t.sql);
    } else {
      setEditingTemplate(null);
      setTemplateName(sql.split('\n')[0].substring(0, 20));
      setTemplateSql(sql);
    }
    setTemplateModalVisible(true);
  };

  const handleDeleteTemplate = (id: string) => {
    const newTemplates = templates.filter((t) => t.id !== id);
    setTemplates(newTemplates);
    localStorage.setItem('sqlTemplates', JSON.stringify(newTemplates));
    setSelectedTemplateId(null);
    message.success('删除成功');
  };

  const handleFormat = () => {
    setSql(formatSql(sql));
    message.success('已格式化');
  };

  const handleTemplateSubmit = () => {
    if (!templateName.trim() || !templateSql.trim()) {
      message.warning('请填写名称和 SQL');
      return;
    }
    if (editingTemplate) {
      const newTemplates = templates.map((t) =>
        t.id === editingTemplate.id ? { id: t.id, name: templateName, sql: templateSql } : t
      );
      setTemplates(newTemplates);
      localStorage.setItem('sqlTemplates', JSON.stringify(newTemplates));
      // If editing the currently selected template, update the SQL editor
      if (selectedTemplateId === editingTemplate.id) {
        setSql(templateSql);
      }
      message.success('更新成功');
    } else {
      const newTemplate = { id: Date.now().toString(), name: templateName, sql: templateSql };
      const newTemplates = [...templates, newTemplate];
      setTemplates(newTemplates);
      localStorage.setItem('sqlTemplates', JSON.stringify(newTemplates));
      message.success('保存成功');
    }
    setTemplateModalVisible(false);
  };

  const handleExport = () => {
    if (!result || result.rows.length === 0) return;
    const headers = result.columns.join(',');
    const csvRows = result.rows.map((row) =>
      result.columns.map((col) => {
        const val = row[col];
        if (val === null || val === undefined) return '';
        const str = String(val);
        return str.includes(',') ? '"' + str.replace(/"/g, '""') + '"' : str;
      }).join(',')
    );
    const csv = [headers, ...csvRows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'query_' + Date.now() + '.csv';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    message.success('导出成功');
  };

  const handleSelectTemplate = (id: string) => {
    setSelectedTemplateId(id);
    const t = templates.find((t) => t.id === id);
    if (t) setSql(t.sql);
  };

  const handleEditTemplate = () => {
    if (selectedTemplateId) {
      const t = templates.find((t) => t.id === selectedTemplateId);
      if (t) handleSaveTemplate(t);
    }
  };

  const columns: ColumnsType<Record<string, unknown>> = result?.columns
    ? result.columns.map((col) => ({
        title: col,
        dataIndex: col,
        key: col,
        width: 150,
        ellipsis: true,
        render: (val: unknown) => {
          if (val === null) return <span style={{ color: '#999' }}>NULL</span>;
          if (val === undefined) return '-';
          return String(val);
        },
      }))
    : [];

  return (
    <div style={{ padding: 24 }}>
      <h2 style={{ marginBottom: 16 }}>数据探索</h2>

      <Card style={{ marginBottom: 16 }}>
        <Space style={{ marginBottom: 16 }}>
          <div>
            <div style={{ marginBottom: 4, fontWeight: 500 }}>数据源</div>
            <Select
              style={{ width: 200 }}
              value={selectedDs}
              onChange={(v) => setSelectedDs(v)}
              placeholder="选择数据源"
            >
              {dataSources.map((ds) => (
                <Option key={ds.id} value={ds.id}>
                  {ds.name} ({ds.db_type})
                </Option>
              ))}
            </Select>
          </div>

          <div>
            <div style={{ marginBottom: 4, fontWeight: 500 }}>模板</div>
            <Space>
              <Select
                style={{ width: 180 }}
                placeholder="选择模板"
                value={selectedTemplateId}
                onChange={handleSelectTemplate}
                allowClear
              >
                {templates.map((t) => (
                  <Option key={t.id} value={t.id}>
                    {t.name}
                  </Option>
                ))}
              </Select>
              {!selectedTemplateId ? (
                <Button size="small" icon={<SaveOutlined />} onClick={() => handleSaveTemplate()}>
                  保存为模板
                </Button>
              ) : (
                <>
                  <span style={{ color: '#666', fontSize: 12 }}>
                    {templates.find(t => t.id === selectedTemplateId)?.name}
                  </span>
                  <Button size="small" icon={<EditOutlined />} onClick={() => handleEditTemplate()}>
                    更新
                  </Button>
                  <Popconfirm title="确定删除?" onConfirm={() => handleDeleteTemplate(selectedTemplateId)}>
                    <Button size="small" danger icon={<DeleteOutlined />}>
                      删除
                    </Button>
                  </Popconfirm>
                </>
              )}
            </Space>
          </div>
        </Space>

        <div style={{ marginBottom: 16 }}>
          <div style={{ marginBottom: 4, fontWeight: 500 }}>SQL 语句</div>
          <SqlEditor
            value={sql}
            onChange={setSql}
            height="180px"
            placeholder="输入 SQL (SELECT only)"
          />
        </div>

        <Space>
          <Button type="primary" icon={<PlayCircleOutlined />} onClick={handleExecute} loading={loading}>
            执行查询
          </Button>
          <Button icon={<BranchesOutlined />} onClick={handleFormat}>
            格式化
          </Button>
          <Button icon={<ClearOutlined />} onClick={() => setSql('')}>
            清空
          </Button>
          {result && result.success && result.rows.length > 0 && (
            <Button icon={<ExportOutlined />} onClick={handleExport}>
              导出 CSV
            </Button>
          )}
        </Space>
      </Card>

      {loading && (
        <Card>
          <div style={{ textAlign: 'center', padding: 40 }}>
            <Spin />
            <p>执行查询中...</p>
          </div>
        </Card>
      )}

      {result && (
        <Card title={result.success ? '查询结果 (' + result.row_count + ' 条)' : '查询错误'}>
          {result.success && result.error && (
            <Alert
              type="error"
              message="SQL 执行错误"
              description={<pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{result.error}</pre>}
              style={{ marginBottom: 16 }}
            />
          )}

          {result.success && result.rows.length > 0 && (
            <Table
              columns={columns}
              dataSource={result.rows}
              rowKey={(_, idx) => String(idx)}
              size="small"
              scroll={{ x: result.columns.length * 150 }}
              pagination={{ pageSize: 50, showSizeChanger: true, showTotal: (t: number) => '共 ' + t + ' 条' }}
            />
          )}

          {result.success && result.rows.length === 0 && (
            <Alert type="warning" message="查询成功，但没有返回任何数据" />
          )}
        </Card>
      )}

      <Modal
        title={editingTemplate ? '编辑模板' : '保存模板'}
        open={templateModalVisible}
        onOk={handleTemplateSubmit}
        onCancel={() => setTemplateModalVisible(false)}
      >
        <Form layout="vertical">
          <Form.Item label="模板名称">
            <Input
              value={templateName}
              onChange={(e) => setTemplateName(e.target.value)}
              placeholder="例如：月度销售汇总"
            />
          </Form.Item>
          <Form.Item label="SQL 语句">
            <TextArea
              value={templateSql}
              onChange={(e) => setTemplateSql(e.target.value)}
              rows={6}
              style={{ fontFamily: 'monospace' }}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
