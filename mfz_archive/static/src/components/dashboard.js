/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart } from "@odoo/owl";

class ArchiveDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            stats: {
                incoming: 0,
                outgoing: 0,
                memo: 0,
                draft: 0,
                in_review: 0,
                approved: 0,
                rejected: 0,
                archived: 0
            },
            loading: true
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        this.state.loading = true;

        // استخدام ORM لطلب البيانات من السيرفر
        try {
            const data = await this.orm.call(
                "archive.management",
                "get_dashboard_data",
                []
            );
            this.state.stats = data;
        } catch (error) {
            console.error("Failed to load dashboard data:", error);
        } finally {
            this.state.loading = false;
        }
    }

    openDocuments(type, domain) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: type,
            res_model: "archive.management",
            domain: domain,
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }
}

ArchiveDashboard.template = "archive_management.Dashboard";

registry.category("actions").add("archive_management.dashboard", ArchiveDashboard);