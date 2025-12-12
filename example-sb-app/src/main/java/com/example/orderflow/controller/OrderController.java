package com.example.orderflow.controller;

import com.example.orderflow.model.Order;
import com.example.orderflow.model.OrderItem;
import com.example.orderflow.model.OrderStatus;
import com.example.orderflow.service.OrderService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/orders")
public class OrderController {

    private final OrderService orderService;

    public OrderController(OrderService orderService) {
        this.orderService = orderService;
    }

    @PostMapping
    public ResponseEntity<Order> createOrder(@Valid @RequestBody Order order) {
        Order created = orderService.createOrder(order);
        return ResponseEntity.status(HttpStatus.CREATED).body(created);
    }

    @GetMapping("/{id}")
    public ResponseEntity<Order> getOrder(@PathVariable Long id) {
        return orderService.getOrder(id)
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }

    @GetMapping("/{id}/details")
    public ResponseEntity<Order> getOrderWithItems(@PathVariable Long id) {
        Order order = orderService.getOrderWithItems(id);
        if (order == null) {
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.ok(order);
    }

    @GetMapping
    public ResponseEntity<List<Order>> getAllOrders(
            @RequestParam(required = false) String customerId,
            @RequestParam(required = false) OrderStatus status,
            @RequestParam(required = false) String region) {

        List<Order> orders;

        if (customerId != null) {
            orders = orderService.getOrdersByCustomer(customerId);
        } else if (status != null) {
            orders = orderService.getOrdersByStatus(status);
        } else if (region != null) {
            orders = orderService.getOrdersByRegion(region);
        } else {
            orders = orderService.getAllOrders();
        }

        return ResponseEntity.ok(orders);
    }

    @PatchMapping("/{id}/status")
    public ResponseEntity<Order> updateStatus(
            @PathVariable Long id,
            @RequestBody Map<String, String> body) {

        String statusStr = body.get("status");
        if (statusStr == null) {
            return ResponseEntity.badRequest().build();
        }

        try {
            OrderStatus newStatus = OrderStatus.valueOf(statusStr.toUpperCase());
            Order updated = orderService.updateOrderStatus(id, newStatus);
            return ResponseEntity.ok(updated);
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().build();
        }
    }

    @PostMapping("/{id}/items")
    public ResponseEntity<Order> addItem(
            @PathVariable Long id,
            @Valid @RequestBody OrderItem item) {
        Order updated = orderService.addItemToOrder(id, item);
        return ResponseEntity.ok(updated);
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> cancelOrder(@PathVariable Long id) {
        orderService.cancelOrder(id);
        return ResponseEntity.noContent().build();
    }

    @GetMapping("/stats")
    public ResponseEntity<Map<String, Long>> getOrderStats() {
        Map<String, Long> stats = Map.of(
                "pending", orderService.countOrdersByStatus(OrderStatus.PENDING),
                "confirmed", orderService.countOrdersByStatus(OrderStatus.CONFIRMED),
                "processing", orderService.countOrdersByStatus(OrderStatus.PROCESSING),
                "shipped", orderService.countOrdersByStatus(OrderStatus.SHIPPED),
                "delivered", orderService.countOrdersByStatus(OrderStatus.DELIVERED),
                "cancelled", orderService.countOrdersByStatus(OrderStatus.CANCELLED)
        );
        return ResponseEntity.ok(stats);
    }
}
