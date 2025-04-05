
/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Layout } from "@web/search/layout";
import { Component, useState, useRef, onMounted, onWillUnmount } from "@odoo/owl";

/**
 * مكون لوحة معلومات نظام إدارة الأرشيف - النسخة المحسنة
 */
export class ArchiveDashboard extends Component {
    setup() {
        // استدعاء الخدمات المطلوبة
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.user = useService("user");

        // مراجع للعناصر في DOM
        this.chartRefs = {
            documentTypesChart: useRef("documentTypesChart"),
            statusChart: useRef("statusChart"),
            monthlyTrendsChart: useRef("monthlyTrendsChart"),
            categoryDistributionChart: useRef("categoryDistributionChart")
        };

        // تهيئة حالة المكون
        this.state = useState({
            stats: {
                incoming: 0,
                outgoing: 0,
                memo: 0,
                pending: 0,
                approved: 0,
                total: 0,
                confidential: 0,
                by_category: [],
                monthly_trends: []
            },
            period: "month", // اليوم، الأسبوع، الشهر، السنة
            recentDocuments: [],
            pendingActions: [],
            topContactors: [], // إضافة جديدة: الجهات الأكثر تفاعلاً
            loading: true,
            error: null,
            expandedSection: null, // للتحكم في توسيع/طي الأقسام
        });

        // تحميل البيانات عند بدء المكون
        onMounted(async () => {
            await this.loadData();
            this.initCharts();
        });

        // تنظيف الرسوم البيانية عند إزالة المكون
        onWillUnmount(() => {
            this.destroyCharts();
        });
    }

    /**
     * تحميل البيانات الإحصائية للوحة المعلومات
     */
    async loadData() {
        this.state.loading = true;
        this.state.error = null;

        try {
            // استدعاء الدالة من النموذج للحصول على البيانات
            const data = await this.orm.call(
                "archive.management",
                "get_dashboard_data",
                [{ period: this.state.period }]
            );
            this.state.stats = data;

            // تحميل المستندات الأخيرة
            this.state.recentDocuments = await this.orm.call(
                "archive.management",
                "get_recent_documents",
                [{ limit: 5 }]
            );

            // تحميل الإجراءات المعلقة
            this.state.pendingActions = await this.orm.call(
                "archive.management",
                "get_pending_actions",
                []
            );
            
            // تحميل الجهات الأكثر تفاعلاً
            this.state.topContactors = await this.orm.call(
                "archive.management",
                "get_top_contactors",
                [{ limit: 5 }]
            );
        } catch (error) {
            console.error("خطأ في تحميل بيانات لوحة المعلومات:", error);
            this.state.error = "تعذر تحميل البيانات. يرجى المحاولة مرة أخرى لاحقاً.";
            this.notification.add(this.state.error, { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    /**
     * تهيئة الرسوم البيانية باستخدام Chart.js
     */
    initCharts() {
        // التأكد من وجود مكتبة Chart.js
        if (!window.Chart) {
            console.error("مكتبة Chart.js غير متوفرة");
            return;
        }

        // تنظيف الرسوم البيانية الموجودة قبل إعادة الإنشاء
        this.destroyCharts();

        // رسم بياني لتوزيع أنواع المستندات
        if (this.chartRefs.documentTypesChart.el) {
            const ctx = this.chartRefs.documentTypesChart.el.getContext('2d');
            this.documentTypesChart = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: ['وارد', 'صادر', 'مذكرات'],
                    datasets: [{
                        data: [
                            this.state.stats.incoming || 0,
                            this.state.stats.outgoing || 0,
                            this.state.stats.memo || 0
                        ],
                        backgroundColor: ['#28a745', '#007bff', '#6c757d']
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            rtl: true
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const label = context.label || '';
                                    const value = context.raw || 0;
                                    const total = context.chart.data.datasets[0].data.reduce((a, b) => a + b, 0);
                                    const percentage = Math.round((value / total) * 100);
                                    return `${label}: ${value} (${percentage}%)`;
                                }
                            }
                        }
                    }
                }
            });
        }

        // رسم بياني لحالات المستندات
        if (this.chartRefs.statusChart.el) {
            const ctx = this.chartRefs.statusChart.el.getContext('2d');
            this.statusChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: ['طلب اعتماد', 'معتمدة'],
                    datasets: [{
                        data: [
                            this.state.stats.pending || 0,
                            this.state.stats.approved || 0
                        ],
                        backgroundColor: ['#ffc107', '#28a745']
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    indexAxis: 'y',
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        x: { beginAtZero: true }
                    }
                }
            });
        }
        
        // رسم بياني للاتجاهات الشهرية
        if (this.chartRefs.monthlyTrendsChart.el && this.state.stats.monthly_trends) {
            const ctx = this.chartRefs.monthlyTrendsChart.el.getContext('2d');
            const monthlyData = this.state.stats.monthly_trends;
            
            this.monthlyTrendsChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: monthlyData.map(item => item.month),
                    datasets: [
                        {
                            label: 'وارد',
                            data: monthlyData.map(item => item.incoming),
                            borderColor: '#28a745',
                            backgroundColor: 'rgba(40, 167, 69, 0.1)',
                            tension: 0.2,
                            fill: true
                        },
                        {
                            label: 'صادر',
                            data: monthlyData.map(item => item.outgoing),
                            borderColor: '#007bff',
                            backgroundColor: 'rgba(0, 123, 255, 0.1)',
                            tension: 0.2,
                            fill: true
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'top',
                        },
                        tooltip: {
                            mode: 'index',
                            intersect: false,
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'عدد المستندات'
                            }
                        }
                    }
                }
            });
        }
        
        // رسم بياني لتوزيع المستندات حسب التصنيف
        if (this.chartRefs.categoryDistributionChart.el && this.state.stats.by_category) {
            const ctx = this.chartRefs.categoryDistributionChart.el.getContext('2d');
            const categoryData = this.state.stats.by_category;
            
            this.categoryDistributionChart = new Chart(ctx, {
                type: 'polarArea',
                data: {
                    labels: categoryData.map(item => item.name),
                    datasets: [{
                        data: categoryData.map(item => item.count),
                        backgroundColor: [
                            'rgba(255, 99, 132, 0.7)',
                            'rgba(54, 162, 235, 0.7)',
                            'rgba(255, 206, 86, 0.7)',
                            'rgba(75, 192, 192, 0.7)',
                            'rgba(153, 102, 255, 0.7)',
                            'rgba(255, 159, 64, 0.7)',
                            'rgba(199, 199, 199, 0.7)',
                        ]
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'right',
                        }
                    }
                }
            });
        }
    }

    /**
     * تنظيف الرسوم البيانية
     */
    destroyCharts() {
        if (this.documentTypesChart) {
            this.documentTypesChart.destroy();
            this.documentTypesChart = null;
        }

        if (this.statusChart) {
            this.statusChart.destroy();
            this.statusChart = null;
        }
        
        if (this.monthlyTrendsChart) {
            this.monthlyTrendsChart.destroy();
            this.monthlyTrendsChart = null;
        }
        
        if (this.categoryDistributionChart) {
            this.categoryDistributionChart.destroy();
            this.categoryDistributionChart = null;
        }
    }

    /**
     * تغيير الفترة الزمنية للإحصائيات
     */
    async changePeriod(period) {
        this.state.period = period;
        await this.loadData();
        this.destroyCharts();
        this.initCharts();
    }

    /**
     * فتح قائمة المستندات
     */
    openDocuments(type, domain) {
        const name = this.getDocumentTypeName(type);

        this.action.doAction({
            type: "ir.actions.act_window",
            name: name,
            res_model: "archive.management",
            domain: domain,
            views: [[false, "list"], [false, "form"]],
            target: "current",
            context: {
                search_default_document_type: type !== 'all' ? type : null,
            }
        });
    }

    /**
     * الحصول على اسم نوع المستند
     */
    getDocumentTypeName(type) {
        const types = {
            'incoming': 'الوارد',
            'outgoing': 'الصادر',
            'memo': 'المذكرات الداخلية',
            'pending': 'المستندات المعلقة',
            'approved': 'المستندات المعتمدة',
            'all': 'جميع المستندات'
        };
        return types[type] || 'المستندات';
    }

    /**
     * فتح نموذج إنشاء مستند جديد
     */
    createNewDocument(type = 'incoming') {
        const documentTypes = {
            'incoming': 'وارد',
            'outgoing': 'صادر',
            'memo': 'مذكرة داخلية'
        };

        this.action.doAction({
            type: "ir.actions.act_window",
            name: `إنشاء ${documentTypes[type] || 'مستند'}`,
            res_model: "archive.management",
            views: [[false, "form"]],
            target: "current",
            context: {
                default_document_type: type
            }
        });
    }

    /**
     * فتح مستند من المستندات الأخيرة
     */
    openDocument(id) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "archive.management",
            res_id: id,
            views: [[false, "form"]],
            target: "current"
        });
    }
    
    /**
     * تبديل حالة توسيع قسم معين
     */
    toggleSection(sectionName) {
        if (this.state.expandedSection === sectionName) {
            this.state.expandedSection = null;
        } else {
            this.state.expandedSection = sectionName;
        }
    }
    
    /**
     * التحقق مما إذا كان القسم موسعاً
     */
    isSectionExpanded(sectionName) {
        return this.state.expandedSection === sectionName;
    }
    
    /**
     * توجيه المستخدم إلى جهة اتصال محددة
     */
    openContactor(id, model) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: model,
            res_id: id,
            views: [[false, "form"]],
            target: "current"
        });
    }
    
    /**
     * فتح محرك البحث المتقدم
     */
    openAdvancedSearch() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "بحث متقدم",
            res_model: "archive.search.wizard",
            views: [[false, "form"]],
            target: "new",
            context: {}
        });
    }
}

// تعريف القالب OWL
ArchiveDashboard.template = "archive_management.Dashboard";

// تسجيل المكون في سجل الإجراءات
registry.category("actions").add("archive_management.dashboard", ArchiveDashboard);

export default ArchiveDashboard;