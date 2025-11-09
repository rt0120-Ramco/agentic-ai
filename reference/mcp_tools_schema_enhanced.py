"""
MCP-Compliant Tool Configuration with API Mapping
================================================

Enhanced MCP tool definitions that include API configuration within the schema.
This creates a single source of truth for both MCP and API configuration.
"""

from mcp.types import Tool
from typing import List, Dict, Any, Tuple
from tool_chain_orchestrator import ToolChainStep

# Removed ToolExamples, ToolPatterns, and ParameterNormalization classes
# These are now handled dynamically by the LLM-driven tool chaining system
class DomainFlowValidator:
    """
    Validates and optimizes tool chains based on business domain knowledge.
    Ensures chains follow logical business flows.
    """
    
    # Business flow patterns
    DOMAIN_FLOWS = {
        "purchase_flow": ["PR", "PO", "GR", "Movement", "Invoice", "Payment"]
    }
    
    # Tool to domain mapping
    TOOL_DOMAIN_MAP = {
        "view_purchase_request": "PR",
        "search_purchase_orders": "PR_to_PO",
        "view_purchase_order": "PO", 
        "help_on_receipt_document": "PO_to_GR",
        "view_receipt_document": "GR",
        "view_movement_details": "Movement",
        "view_inspection_details": "Inspection",
        "view_subcontract_request": "SCR"
    }
    
    def validate_chain(self, tool_chain: List[ToolChainStep]) -> Tuple[bool, str, List[ToolChainStep]]:
        """
        Validate and optimize a tool chain based on domain flows.
        
        Returns:
            (is_valid, message, optimized_chain)
        """
        if not tool_chain:
            return False, "Empty tool chain", []
        
        # Check for logical flow
        domain_sequence = [self.TOOL_DOMAIN_MAP.get(step.tool_name, step.tool_name) for step in tool_chain]
        
        # Validate business logic
        validation_result = self._validate_business_logic(domain_sequence)
        if not validation_result[0]:
            return validation_result[0], validation_result[1], tool_chain
        
        # Optimize chain if possible
        optimized_chain = self._optimize_chain(tool_chain)
        
        return True, "Chain validated and optimized", optimized_chain
    
    def _validate_business_logic(self, domain_sequence: List[str]) -> Tuple[bool, str]:
        """Validate the domain sequence follows business logic"""
        
        # Check for invalid reverse flows
        invalid_patterns = [
            ["GR", "PO"],  # Can't go from GR back to PO
            ["Invoice", "GR"],  # Can't go from Invoice back to GR
            ["Payment", "Invoice"]  # Can't go from Payment back to Invoice
        ]
        
        for i in range(len(domain_sequence) - 1):
            current_domain = domain_sequence[i]
            next_domain = domain_sequence[i + 1]
            
            if [current_domain, next_domain] in invalid_patterns:
                return False, f"Invalid business flow: {current_domain} → {next_domain}"
        
        return True, "Valid business flow"
    
    def _optimize_chain(self, tool_chain: List[ToolChainStep]) -> List[ToolChainStep]:
        """Optimize the tool chain by removing redundant steps"""
        
        # Remove redundant consecutive calls to same tool
        optimized = []
        prev_tool = None
        
        for step in tool_chain:
            if step.tool_name != prev_tool:
                optimized.append(step)
                prev_tool = step.tool_name
        
        return optimized

def get_mcp_tools_with_api_config() -> List[Dict[str, Any]]:
    """
    Return MCP tools with embedded API configuration.
    This eliminates the need for separate API configuration files.
    """
    
    # Global document flow metadata for LLM understanding
    document_flow = {
        "business_flows": {
            "procurement_to_payment": [
                "PR", "PO", "GR", "Movement", "Invoice", "Payment"
            ]
        },
        "flow_descriptions": {
            "PR": "Purchase Request - Initial procurement requirement specification",
            "PO": "Purchase Order - Formal order to supplier",
            "GR": "Goods Receipt - Delivery confirmation and acceptance",
            "GR Movement": "GR Stock Movement to Warehouse operations",
            "Invoice": "Supplier Invoice - Billing for goods/services",
            "Payment": "Payment Processing - Financial settlement"
        },
        "chaining_rules": [
            "PR can lead to PO (via search_purchase_orders)",
            "PO can lead to GR (via help_on_receipt_document)",
            "GR can lead to Movement/Inspection (direct tools)",
            "Invoice can be traced back to PO/GR",
            "Payment can be traced back to Invoice"
        ]
    }
    
    return [
        {
            "tool": Tool(
                name="view_inspection_details",
                description="Retrieve inspection results and quality control data for goods receipts, including inspection status, quality parameters, and compliance information",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "receipt_no": {
                            "type": "string",
                            "description": "Receipt number for inspection (e.g., '1041', 'GR123', 'REC456')",
                            "examples": ["1041", "GR123", "REC456"]
                        }
                    },
                    "required": ["receipt_no"]
                }
            ),
            "api_config": {
                "service_path": "/purchase/gr_ser/v1",
                "endpoint": "/ViewInspectionDetails",
                "param_map": {"receipt_no": "Receiptno"},
                "component": "GOODSRETURNNOTES",
                "http_method": "GET",
                "document_type": {
                    "keywords": ["inspection", "quality", "qc"],
                    "description": "inspection, quality control, QC operations"
                },
                "output_schema": {
                    "InspectionDetails": {
                        "type": "object",
                        "properties": {
                            "ReceiptNo": {"type": "string", "description": "Receipt number"},
                            "InspectionStatus": {"type": "string", "description": "Quality inspection status"},
                            "QualityParameters": {"type": "array", "description": "Quality control parameters"},
                            "ComplianceStatus": {"type": "string", "description": "Compliance verification status"},
                            "InspectorId": {"type": "string", "description": "Inspector identifier"},
                            "InspectionDate": {"type": "string", "description": "Date of inspection"}
                        }
                    }
                },
                "parameter_normalization": {
                    "receipt_no": "upper"
                },
                "runtime_defaults": {
                    "include_history": False,
                    "format": "detailed"
                },
                "output_to_input_hints": {
                    "ReceiptNo": [
                        {"tool": "view_movement_details", "param": "receipt_no"},
                        {"tool": "view_receipt_document", "param": "receipt_no"}
                    ]
                }
            }
        },
        
        {
            "tool": Tool(
                name="view_movement_details", 
                description="Get stock movement and warehouse operation details for goods receipts, including transfer history, location changes, and inventory updates",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "receipt_no": {
                            "type": "string",
                            "description": "Receipt number for movement details (e.g., '1041', 'GR123', 'REC456')",
                            "examples": ["1041", "GR123", "REC456"]
                        }
                    },
                    "required": ["receipt_no"]
                }
            ),
            "api_config": {
                "service_path": "/purchase/GOODSRETURNNOTES/v1",
                "endpoint": "/ViewMovementDetails", 
                "param_map": {"receipt_no": "Receiptno"},
                "component": "GOODSRETURNNOTES",
                "http_method": "GET",
                "document_type": {
                    "keywords": ["movement", "stock", "inventory"],
                    "description": "stock movement, warehouse operations"
                },
                "output_schema": {
                    "MovementDetails": {
                        "type": "object",
                        "properties": {
                            "ReceiptNo": {"type": "string", "description": "Receipt number"},
                            "MovementHistory": {"type": "array", "description": "Stock movement transactions"},
                            "CurrentLocation": {"type": "string", "description": "Current warehouse location"},
                            "TransferDetails": {"type": "array", "description": "Location transfer history"},
                            "InventoryUpdates": {"type": "array", "description": "Inventory update records"},
                            "WarehouseOperations": {"type": "array", "description": "Warehouse operation logs"}
                        }
                    }
                },
                "parameter_normalization": {
                    "receipt_no": "upper"
                },
                "runtime_defaults": {
                    "include_transfers": True,
                    "history_depth": 30
                },
                "output_to_input_hints": {
                    "ReceiptNo": [
                        {"tool": "view_inspection_details", "param": "receipt_no"},
                        {"tool": "view_receipt_document", "param": "receipt_no"}
                    ]
                },

            }
        },
        
        {
            "tool": Tool(
                name="view_purchase_order",
                description="Retrieve comprehensive purchase order information including supplier details, line items, pricing, delivery schedules, and approval status",
                inputSchema={
                    "type": "object", 
                    "properties": {
                        "po_number": {
                            "type": "string",
                            "description": "Purchase order number (e.g., 'JSLTEST46', 'PO123', 'ORD789')",
                            "examples": ["JSLTEST46", "PO123", "ORD789"]
                        },
                        "amendment_no": {
                            "type": "string",
                            "description": "Amendment number for the purchase order",
                            "default": "0",
                            "examples": ["0", "1", "2"]
                        }
                    },
                    "required": ["po_number"]
                }
            ),
            "api_config": {
                "service_path": "/purchase/po_ser/v1",
                "endpoint": "/ViewPO",
                "param_map": {"po_number": "Ponohdr", "amendment_no": "AmendmentNo"},
                "component": "PO_SER",
                "http_method": "GET",
                "document_type": {
                    "keywords": ["po", "purchase_order", "purchase order"],
                    "description": "PO/purchase order"
                },
                "output_schema": {
                    "PurchaseOrderDetails": {
                        "type": "object",
                        "properties": {
                            "PoNo": {"type": "string", "description": "Purchase order number"},
                            "SupplierCode": {"type": "string", "description": "Supplier identifier"},
                            "SupplierName": {"type": "string", "description": "Supplier name"},
                            "PoAmount": {"type": "number", "description": "Total PO amount"},
                            "PoDate": {"type": "string", "description": "PO creation date"},
                            "PoStatus": {"type": "string", "description": "Current PO status"},
                            "LineItems": {"type": "array", "description": "PO line item details"},
                            "DeliverySchedule": {"type": "array", "description": "Delivery timeline"},
                            "ApprovalStatus": {"type": "string", "description": "Approval workflow status"},
                            "PrNumbers": {"type": "array", "description": "Associated PR numbers"},
                            "AmendmentNo": {"type": "string", "description": "Amendment number"}
                        }
                    }
                },
                "parameter_normalization": {
                    "po_number": "upper"
                },
                "runtime_defaults": {
                    "include_line_items": True,
                    "include_history": False
                },
                "output_to_input_hints": {
                    "PoNo": [
                        {"tool": "help_on_receipt_document", "param": "ref_doc_no_from"},
                        {"tool": "help_on_receipt_document", "param": "ref_doc_no_to"},
                        {"tool": "view_po_pr_coverage", "param": "po_number"}
                    ]
                },
                }
        },
        {
            "tool": Tool(
                name="view_purchase_request",
                description="Get purchase requisition details including requester information, approval workflow status, budget allocation, and item specifications", 
                inputSchema={
                    "type": "object",
                    "properties": {
                        "pr_number": {
                            "type": "string",
                            "description": "Purchase request number (e.g., 'PR123', 'REQ456', 'JSLTEST46')",
                            "examples": ["PR123", "REQ456", "JSLTEST46"]
                        }
                    },
                    "required": ["pr_number"]
                }
            ),
            "api_config": {
                "service_path": "/purchase/PRA/v1",
                "endpoint": "/ViewPurchaseRequest",
                "param_map": {"pr_number": "PrNo"},
                "component": "Pur_Req_SER",
                "http_method": "GET",
                "document_type": {
                    "keywords": ["pr", "purchase_request", "purchase request", "requisition"],
                    "description": "PR, purchase request, requisition operations"
                },
                "output_schema": {
                    "PurchaseRequestDetails": {
                        "type": "object",
                        "properties": {
                            "PrNo": {"type": "string", "description": "Purchase request number"},
                            "RequesterInfo": {"type": "object", "description": "Requester details"},
                            "ApprovalStatus": {"type": "string", "description": "Current approval status"},
                            "WorkflowState": {"type": "string", "description": "Workflow stage"},
                            "BudgetAllocation": {"type": "object", "description": "Budget information"},
                            "ItemSpecifications": {"type": "array", "description": "Requested item details"},
                            "Priority": {"type": "string", "description": "Request priority"},
                            "CreatedDate": {"type": "string", "description": "PR creation date"},
                            "RequiredDate": {"type": "string", "description": "Required delivery date"}
                        }
                    }
                },
                "parameter_normalization": {
                    "pr_number": "upper"
                },
                "runtime_defaults": {
                    "include_workflow": True,
                    "include_budget": True
                },
                "output_to_input_hints": {
                    "PrNo": [
                        {"tool": "search_purchase_orders", "param": "pr_no_from"},
                        {"tool": "search_purchase_orders", "param": "pr_no_to"}
                    ]
                },
                }
        },
        {
            "tool": Tool(
                name="search_purchase_orders",
                description="Search for purchase orders based on various criteria including PR numbers, PO dates, suppliers, etc. Returns list of matching purchase orders with their details.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "pr_no_from": {
                            "type": "string",
                            "description": "Purchase request number from (e.g., 'PR123', 'REQ456', 'JSLTEST46')",
                            "examples": ["PR123", "REQ456", "JSLTEST46"]
                        },
                        "pr_no_to": {
                            "type": "string", 
                            "description": "Purchase request number to (same as pr_no_from for single PR search)",
                            "examples": ["PR123", "REQ456", "JSLTEST46"]
                        },
                        "po_no_from": {
                            "type": "string",
                            "description": "Purchase order number from (e.g., 'JSLTEST46', 'PO123', 'ORD789')",
                            "examples": ["JSLTEST46", "PO123", "ORD789"]
                        },
                        "po_no_to": {
                            "type": "string",
                            "description": "Purchase order number to (same as po_no_from for single PO search)",
                            "examples": ["JSLTEST46", "PO123", "ORD789"]
                        },
                        "supplier_code": {
                            "type": "string",
                            "description": "Supplier code for filtering",
                            "examples": ["SUP001", "VENDOR123"]
                        },
                        "from_po_date": {
                            "type": "string",
                            "format": "date",
                            "description": "From PO date (YYYY-MM-DD format)",
                            "examples": ["2024-01-01", "2024-11-01"]
                        },
                        "to_po_date": {
                            "type": "string",
                            "format": "date", 
                            "description": "To PO date (YYYY-MM-DD format)",
                            "examples": ["2024-12-31", "2024-11-30"]
                        }
                    },
                    "required": []
                }
            ),
            "api_config": {
                "service_path": "/purchase/po_ser/v1",
                "endpoint": "/SearchPO",
                "param_map": {
                    "pr_no_from": "PrNoFrom",
                    "pr_no_to": "PrNoTo",
                    "po_no_from": "FromPoNo",
                    "po_no_to": "ToPoNo",
                    "supplier_code": "SupplierCodeIn",
                    "from_po_date": "FromPoDate",
                    "to_po_date": "ToPoDate"
                },
                "component": "PO_SER",
                "http_method": "GET",
                "document_type": {
                    "keywords": ["search", "po", "purchase_order", "pr", "purchase_request"],
                    "description": "Search purchase orders, PO/PR search operations"
                },
                "output_schema": {
                    "SearchPOResult": {
                        "type": "array",
                        "items": {
                            "PoNo": "string",
                            "SupplierCodeOut": "string", 
                            "SupplierName": "string",
                            "POAmount": "number",
                            "PoDate": "string",
                            "PoStatusOut": "string",
                            "PrNo": "string"
                        }
                    }
                },
                "parameter_normalization": {
                    "pr_no_from": "upper",
                    "pr_no_to": "upper",
                    "po_no_from": "upper",
                    "po_no_to": "upper",
                    "supplier_code": "upper"
                },
                "runtime_defaults": {
                    "max_results": 100,
                    "include_details": True
                },
                "output_to_input_hints": {
                    "PoNo": [
                        {"tool": "view_purchase_order", "param": "po_number"},
                        {"tool": "help_on_receipt_document", "param": "ref_doc_no_from"},
                        {"tool": "help_on_receipt_document", "param": "ref_doc_no_to"}
                    ]
                },
                }
        },
        {
            "tool": Tool(
                name="help_on_receipt_document",
                description="Search and retrieve receipt document details based on reference document numbers (typically PO numbers). Returns goods receipt information including quantities, dates, and status.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ref_doc_no_from": {
                            "type": "string",
                            "description": "Reference document number from (typically PO number like 'JSLTEST46', 'PO123')",
                            "examples": ["JSLTEST46", "PO123", "ORD789"]
                        },
                        "ref_doc_no_to": {
                            "type": "string",
                            "description": "Reference document number to (same as ref_doc_no_from for single document search)",
                            "examples": ["JSLTEST46", "PO123", "ORD789"]
                        },
                        "receipt_no_from": {
                            "type": "string",
                            "description": "Receipt number from (e.g., '1041', 'GR123', 'REC456')",
                            "examples": ["1041", "GR123", "REC456"]
                        },
                        "receipt_no_to": {
                            "type": "string",
                            "description": "Receipt number to (same as receipt_no_from for single receipt search)",
                            "examples": ["1041", "GR123", "REC456"]
                        },
                        "supplier_code": {
                            "type": "string",
                            "description": "Supplier code for filtering",
                            "examples": ["SUP001", "VENDOR123"]
                        },
                        "receipt_date_from": {
                            "type": "string",
                            "format": "date",
                            "description": "From receipt date (YYYY-MM-DD format)",
                            "examples": ["2024-01-01", "2024-11-01"]
                        },
                        "receipt_date_to": {
                            "type": "string",
                            "format": "date",
                            "description": "To receipt date (YYYY-MM-DD format)",
                            "examples": ["2024-12-31", "2024-11-30"]
                        }
                    },
                    "required": []
                }
            ),
            "api_config": {
                "service_path": "/purchase/GOODSRETURNNOTES/v1",
                "endpoint": "/HelpOnReceiptDocument",
                "param_map": {
                    "ref_doc_no_from": "RefDocNoFrom",
                    "ref_doc_no_to": "RefDocNoTo", 
                    "receipt_no_from": "ReceiptNoFrom",
                    "receipt_no_to": "Receiptnoto",
                    "supplier_code": "SupplierCode",
                    "receipt_date_from": "ReceiptDateFrom",
                    "receipt_date_to": "ReceiptDateTo"
                },
                "component": "GR_SER",
                "http_method": "GET",
                "document_type": {
                    "keywords": ["receipt", "gr", "goods_receipt", "help"],
                    "description": "Receipt document search, goods receipt operations"
                },
                "output_schema": {
                    "SearchResults": {
                        "type": "array",
                        "items": {
                            "ReceiptNo": "string",
                            "RefDocNo": "string",
                            "ItemCodeml": "string",
                            "ItemDescml": "string",
                            "ReceivedQty": "number",
                            "AcceptedQty": "number",
                            "RejectedQty": "number",
                            "SupplierCodeml": "string",
                            "SupplierNameml": "string",
                            "Date": "string",
                            "ReceiptLineNo": "number"
                        }
                    }
                },
                "parameter_normalization": {
                    "ref_doc_no_from": "upper",
                    "ref_doc_no_to": "upper",
                    "receipt_no_from": "upper",
                    "receipt_no_to": "upper",
                    "supplier_code": "upper"
                },
                "runtime_defaults": {
                    "max_results": 200,
                    "include_line_details": True
                },
                "output_to_input_hints": {
                    "ReceiptNo": [
                        {"tool": "view_receipt_document", "param": "receipt_no"},
                        {"tool": "view_movement_details", "param": "receipt_no"},
                        {"tool": "view_inspection_details", "param": "receipt_no"}
                    ],
                    "RefDocNo": [
                        {"tool": "view_purchase_order", "param": "po_number"}
                    ]
                },
                }
        },
        {
            "tool": Tool(
                name="view_receipt_document",
                description="Access goods receipt documentation including delivery details, received quantities, quality notes, and supplier confirmation",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "receipt_no": {
                            "type": "string", 
                            "description": "Receipt document number (e.g., 'GR123', '1041', 'REC456')",
                            "examples": ["1041", "GR123", "REC456"]
                        }
                    },
                    "required": ["receipt_no"]
                }
            ),
            "api_config": {
                "service_path": "",
                "endpoint": "/ViewReceiptDocument",
                "param_map": {"receipt_no": "ReceiptNo"},
                "component": "GR_SER",
                "http_method": "GET",
                "document_type": {
                    "keywords": ["receipt", "gr", "goods receipt"],
                    "description": "receipt document, goods receipt operations"
                },
                "output_schema": {
                    "ReceiptDocumentDetails": {
                        "type": "object",
                        "properties": {
                            "ReceiptNo": {"type": "string", "description": "Receipt document number"},
                            "DeliveryDetails": {"type": "object", "description": "Delivery information"},
                            "ReceivedQuantities": {"type": "array", "description": "Received quantity details"},
                            "QualityNotes": {"type": "string", "description": "Quality inspection notes"},
                            "SupplierConfirmation": {"type": "object", "description": "Supplier acknowledgment"},
                            "PoNumbers": {"type": "array", "description": "Related PO numbers"},
                            "ReceiptDate": {"type": "string", "description": "Receipt date"},
                            "Status": {"type": "string", "description": "Receipt status"}
                        }
                    }
                },
                "parameter_normalization": {
                    "receipt_no": "upper"
                },
                "runtime_defaults": {
                    "include_quality_notes": True,
                    "include_supplier_info": True
                },
                "output_to_input_hints": {
                    "ReceiptNo": [
                        {"tool": "view_movement_details", "param": "receipt_no"},
                        {"tool": "view_inspection_details", "param": "receipt_no"}
                    ],
                    "PoNumbers": [
                        {"tool": "view_purchase_order", "param": "po_number"}
                    ],
                    "SupplierCode": [
                        {"tool": "search_purchase_orders", "param": "supplier_code"},
                        {"tool": "view_invoice_details", "param": "supplier_code"}
                    ]
                },
                }
        },
        {
            "tool": Tool(
                name="view_subcontract_request",
                description="Retrieve subcontracting and job work request information including vendor details, work specifications, timelines, and approval status",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "scr_number": {
                            "type": "string",
                            "description": "Subcontract request number (e.g., 'SCR123', 'SUB456', 'JOB789')",
                            "examples": ["SCR123", "SUB456", "JOB789"]
                        }
                    },
                    "required": ["scr_number"]
                }
            ),
            "api_config": {
                "service_path": "/purchase/sc_req_ser/v1",
                "endpoint": "/ViewSubcontractRequest", 
                "param_map": {"scr_number": "ScrNo"},
                "component": "SC_REQ_SER",
                "http_method": "GET",
                "document_type": {
                    "keywords": ["subcontract", "scr", "job work"],
                    "description": "subcontract, job work operations"
                },
                "output_schema": {
                    "SubcontractRequestDetails": {
                        "type": "object",
                        "properties": {
                            "ScrNo": {"type": "string", "description": "Subcontract request number"},
                            "VendorDetails": {"type": "object", "description": "Vendor information"},
                            "WorkSpecifications": {"type": "array", "description": "Job work specifications"},
                            "Timelines": {"type": "object", "description": "Project timeline"},
                            "ApprovalStatus": {"type": "string", "description": "Current approval status"},
                            "ContractValue": {"type": "number", "description": "Contract amount"},
                            "WorkOrderNo": {"type": "string", "description": "Generated work order"},
                            "DeliverySchedule": {"type": "array", "description": "Delivery milestones"}
                        }
                    }
                },
                "parameter_normalization": {
                    "scr_number": "upper"
                },
                "runtime_defaults": {
                    "include_vendor_details": True,
                    "include_timeline": True
                },
                "output_to_input_hints": {
                    "ScrNo": [
                        {"tool": "track_subcontract_progress", "param": "scr_number"}
                    ],
                    "VendorCode": [
                        {"tool": "search_subcontracts", "param": "vendor_code"}
                    ],
                    "WorkOrderNo": [
                        {"tool": "view_work_order", "param": "work_order_no"}
                    ]
                },
                }
        },
        {
            "tool": Tool(
                name="ViewTCDDetails",
                description="Get TCD (Tax, Charge, Discount) configuration details including rates, basis, and variant information. Use this tool when user asks for TCD details with codes like '10P', 'VAT5', etc.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "Tcdcodehdr": {
                            "type": "string",
                            "description": "TCD Code (extract from user query - e.g., '10P', 'VAT5', 'DISC10'). Case-insensitive.",
                            "examples": ["10P", "VAT5", "DISC10", "TAX15"]
                        }
                    },
                    "required": ["Tcdcodehdr"]
                }
            ),
            "api_config": {
                "service_path": "/purchase/tcd/v1",
                "endpoint": "/ViewTCDDetails",
                "param_map": {"Tcdcodehdr": "Tcdcodehdr"},
                "component": "TCD_SER",
                "http_method": "GET",
                "parameter_normalization": {
                    "Tcdcodehdr": "upper"
                }
            }
        },
        
        # Example of a tool with multiple parameters - CORRECTED VERSION
        {
            "tool": Tool(
                name="GetStockDetails",
                description="Get current stock details including availability, location, and status information for inventory items",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ItemCode": {
                            "type": "string",
                            "description": "Item Code - Item/Material code for stock inquiry (e.g., 'ITEM001', 'MAT123')",
                            "examples": ["ITEM001", "MAT123", "PROD456"]
                        },
                        "StockStatus": {
                            "type": "string",
                            "description": "Stock status filter (e.g., 'Acc' for Accepted, 'Rej' for Rejected, 'All' for all statuses)",
                            "examples": ["Acc", "Rej", "All", "Pending"],
                            "default": "All"
                        },
                        "WarehouseCode": {
                            "type": "string",
                            "description": "Warehouse/Storage code (optional filter)",
                            "examples": ["WH001", "STORE01", "LOC123"],
                            "default": ""
                        }
                    },
                    "required": ["ItemCode","WarehouseCode"]  # Only ItemCode is required, others are optional
                }
            ),
            "api_config": {
                "service_path": "/v1",
                "endpoint": "/GetStockDetails",
                "param_map": {
                    "ItemCode": "ItemCode",
                    "StockStatus": "StockStatus", 
                    "WarehouseCode": "WarehouseCode"
                },
                "component": "STKMNT_SER",
                "http_method": "GET"
            }
        },
        
        # New API: ViewPOPRCoverage - GET with multiple parameters
        {
            "tool": Tool(
                name="view_po_pr_coverage",
                description="View PO-PR coverage details including schedule information, balance quantities, and supplier details for purchase order tracking",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "po_number": {
                            "type": "string",
                            "description": "Purchase order number for coverage analysis (e.g., 'PO123', 'JSLTEST46')",
                            "examples": ["PO123", "JSLTEST46", "ORD789"]
                        },
                        "amendment_no": {
                            "type": "integer",
                            "description": "Amendment number for the purchase order",
                            "examples": [0, 1, 2],
                            "default": 0
                        },
                        "guid": {
                            "type": "string",
                            "description": "GUID identifier for the request (optional)",
                            "examples": ["12345-67890-abcde"],
                            "default": ""
                        }
                    },
                    "required": ["po_number", "amendment_no"]
                }
            ),
            "api_config": {
                "service_path": "/purchase/po_ser/v1",
                "endpoint": "/ViewPOPRCoverage",
                "param_map": {
                    "po_number": "Ponohdr",
                    "amendment_no": "AmendmentNo",
                    "guid": "Guid"
                },
                "component": "PO_SER",
                "http_method": "GET"
            }
        },
        
        # New API: ApprovePO - POST with complex nested schema and runtime defaults
        {
            "tool": Tool(
                name="approve_purchase_order",
                description="Approve purchase orders with approval details including remarks, dates, and line-item level approvals",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "po_number": {
                            "type": "string",
                            "description": "Purchase order number to approve. CRITICAL: Preserve the EXACT text as typed by user, including all backslashes and special characters. Do NOT interpret backslashes as escape sequences. If user types 'PO\\10005624\\2007', extract it exactly as 'PO\\10005624\\2007'. Examples: 'PO/10005624/2007', 'PO\\10005624\\2007', 'JSLTEST46', 'ORD/123/456'",
                            "examples": ["PO123", "JSLTEST46", "ORD789", "PO/10005624/2007", "PO\\10005624\\2007", "DOC/456/2024"],
                            "pattern": "^[A-Za-z0-9/\\\\\\-_]+$"
                        },
                        "approval_date": {
                            "type": "string",
                            "description": "Date of approval in YYYY-MM-DD format (optional - defaults to current system date)",
                            "format": "date",
                            "examples": ["2024-10-30", "2024-11-01"]
                        },
                        "remarks": {
                            "type": "string",
                            "description": "Approval remarks or comments (optional)",
                            "examples": ["Approved by manager", "Emergency approval", "Standard approval"],
                            "default": ""
                        },
                        "mode_flag": {
                            "type": "string",
                            "description": "Mode flag for approval process (optional - defaults to 'Z')",
                            "examples": ["A", "M", "U", "Z"],
                            "default": "Z"
                        },
                        "timestamp": {
                            "type": "integer",
                            "description": "Timestamp for the approval action (optional - defaults to 1)",
                            "examples": [1698745200, 1698831600, 1],
                            "default": 1
                        },
                        "flag": {
                            "type": "string",
                            "description": "Control flag for the approval process",
                            "examples": ["Y", "N"],
                            "default": "Y"
                        }
                    },
                    "required": ["po_number"]  # Only po_number is mandatory
                }
            ),
            "api_config": {
                "service_path": "/purchase/po_ser/v1",
                "endpoint": "/ApprovePO",
                "param_map": {
                    "po_number": "Ponomlt",
                    "approval_date": "Approvaldate",
                    "remarks": "Remarksml",
                    "mode_flag": "Modeflag",
                    "timestamp": "Timestampnew",
                    "flag": "Flag"
                },
                "component": "PO_SER",
                "http_method": "POST",
                "request_body_template": {
                    "Flag": "{{flag}}",
                    "ApprovepoMlin": [
                        {
                            "Approvaldate": "{{approval_date}}",
                            "Modeflag": "{{mode_flag}}",
                            "Ponomlt": "{{po_number}}",
                            "Remarksml": "{{remarks}}",
                            "Timestampnew": "{{timestamp}}"
                        }
                    ]
                },
                "runtime_defaults": {
                    "approval_date": "CURRENT_DATE",
                    "mode_flag": "Z",
                    "timestamp": 1,
                    "flag": "Y",
                    "remarks": ""
                }
            }
        },
        
        # Natural Language Query Tool - Server-side LLM processing
        {
            "tool": Tool(
                name="natural_language_query",
                description="Process natural language queries and automatically determine which API tools to call. This is the main entry point for human-readable requests.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language query from the user. Examples: 'show details of PO\\10005624\\2007', 'approve purchase order PO123', 'view movement for receipt 1041'",
                            "examples": [
                                "show details of PO\\10005624\\2007",
                                "approve purchase order PO123",
                                "view movement for receipt 1041",
                                "get inspection details for order 456",
                                "what movement happened for item ABC"
                            ]
                        }
                    },
                    "required": ["query"]
                }
            ),
            "api_config": {
                "service_path": "",  # No direct API call - this is processed server-side
                "endpoint": "",
                "param_map": {},
                "component": "NLP_PROCESSOR",
                "http_method": "INTERNAL",
                "is_natural_language": True  # Flag to indicate this needs LLM processing
            }
        }
    ]

def get_mcp_tools() -> List[Tool]:
    """
    Backward compatibility function - returns just the Tool objects.
    """
    tools_with_config = get_mcp_tools_with_api_config()
    return [item["tool"] for item in tools_with_config]

def get_tools_in_mcp_format() -> List[Dict[str, Any]]:
    """
    Get tools in the exact MCP protocol format.
    This eliminates the need for _convert_tools_to_mcp_format method.
    """
    tools_with_config = get_mcp_tools_with_api_config()
    return [
        {
            "name": item["tool"].name,
            "description": item["tool"].description,
            "inputSchema": item["tool"].inputSchema
        }
        for item in tools_with_config
    ]

def get_api_config_for_tool(tool_name: str) -> Dict[str, Any]:
    """
    Get API configuration for a specific tool.
    """
    tools_with_config = get_mcp_tools_with_api_config()
    for item in tools_with_config:
        if item["tool"].name == tool_name:
            return item["api_config"]
    return {}

def get_document_type_mapping() -> Dict[str, str]:
    """
    Generate dynamic document type to tool name mapping.
    """
    mapping = {}
    tools_with_config = get_mcp_tools_with_api_config()
    
    for item in tools_with_config:
        tool_name = item["tool"].name
        doc_type_info = item["api_config"].get("document_type", {})
        keywords = doc_type_info.get("keywords", [])
        
        for keyword in keywords:
            mapping[keyword] = tool_name
    
    return mapping

def generate_nlp_prompt_section() -> str:
    """
    Generate the document type identification section for NLP prompts dynamically.
    Now includes actual parameter names for each tool.
    """
    tools_with_config = get_mcp_tools_with_api_config()
    
    lines = [
        "AVAILABLE TOOLS AND PARAMETERS:",
        "================================"
    ]
    
    for item in tools_with_config:
        tool = item["tool"]
        doc_type_info = item["api_config"].get("document_type", {})
        keywords = doc_type_info.get("keywords", [])
        
        # Tool description
        lines.append(f"\n{tool.name}:")
        lines.append(f"  Description: {tool.description}")
        
        # Document type indicators
        if keywords:
            keyword_list = ", ".join(f'"{kw}"' for kw in keywords)
            lines.append(f"  Keywords: {keyword_list}")
        
        # Required parameters
        properties = tool.inputSchema.get("properties", {})
        required = tool.inputSchema.get("required", [])
        
        if properties:
            lines.append("  Parameters:")
            for param_name, param_info in properties.items():
                param_desc = param_info.get("description", "")
                param_type = param_info.get("type", "string")
                examples = param_info.get("examples", [])
                default_value = param_info.get("default")
                
                param_line = f"    - {param_name} ({param_type}): {param_desc}"
                
                if default_value is not None:
                    # Format default value according to type
                    if param_type == "string":
                        param_line += f" [default: \"{default_value}\"]"
                    else:
                        param_line += f" [default: {default_value}]"
                        
                if examples:
                    param_line += f" (examples: {', '.join(str(ex) for ex in examples[:3])})"
                    
                if param_name in required:
                    param_line += " *REQUIRED*"
                    
                lines.append(param_line)
    
    lines.extend([
        "\nPARAMETER EXTRACTION RULES:",
        "============================",
        "- For movement queries: extract document number → receipt_no parameter",
        "- For PO queries: extract PO number → po_number parameter", 
        "- For PR queries: extract PR number → pr_number parameter",
        "- For inspection queries: extract receipt number → receipt_no parameter",
        "- For receipt queries: extract receipt number → receipt_no parameter",
        "- For subcontract queries: extract SCR number → scr_number parameter",
        "",
        "TYPE REQUIREMENTS:",
        "==================",
        "- Use the exact type specified for each parameter above",
        "- String parameters: use quotes (\"value\")",
        "- Integer parameters: use numbers without quotes (123)",
        "- Boolean parameters: use true/false without quotes",
        "- Follow the [default: value] format shown for each parameter",
        "",
        "EXAMPLE RESPONSES:",
        "=================",
        "view_purchase_order: {\"tool_name\": \"view_purchase_order\", \"parameters\": {\"po_number\": \"JSLDR2\", \"amendment_no\": \"0\"}}",
        "view_po_pr_coverage: {\"tool_name\": \"view_po_pr_coverage\", \"parameters\": {\"po_number\": \"JSLDR2\", \"amendment_no\": 0}}",
        "view_movement_details: {\"tool_name\": \"view_movement_details\", \"parameters\": {\"receipt_no\": \"1041\"}}",
        "",
        "CRITICAL: Always use the exact parameter names and types shown above!"
    ])
    
    return "\n".join(lines)

def get_all_api_configs() -> Dict[str, Dict[str, Any]]:
    """
    Get all API configurations as a dictionary keyed by tool name.
    This can replace the tool_config in ramco_api_service.py
    Enhanced to include default values from JSON schema.
    """
    tools_with_config = get_mcp_tools_with_api_config()
    result = {}
    
    for item in tools_with_config:
        tool = item["tool"]
        api_config = item["api_config"].copy()
        
        # Extract default values from tool schema
        schema_defaults = {}
        properties = tool.inputSchema.get("properties", {})
        
        for param_name, param_info in properties.items():
            if "default" in param_info:
                schema_defaults[param_name] = param_info["default"]
        
        # Add schema defaults to api_config
        if schema_defaults:
            api_config["schema_defaults"] = schema_defaults
        
        result[tool.name] = api_config
    
    return result

# Example of how to add a new API - just add to the list above:
"""
{
    "tool": Tool(
        name="ViewTCDDetails",
        description="Get TCD Details",
        inputSchema={
            "type": "object",
            "properties": {
                "Tcdcodehdr": {
                    "type": "string",
                    "description": "TCD Code"
                }
            },
            "required": ["Tcdcodehdr"]
        }
    ),
    "api_config": {
        "service_path": "/purchase/tcd/v1/",
        "endpoint": "/ViewTCDDetails",
        "param_map": {"Tcdcodehdr": "Tcdcodehdr"},
        "component": "TCD_SER",
        "http_method": "GET"
    }
}
"""