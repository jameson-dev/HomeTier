// Categories Management JavaScript Functions

let currentCategories = [];
let currentView = 'grid';

// Load and display categories
async function loadCategories() {
    try {
        const response = await fetch('/api/categories');
        const result = await response.json();
        
        if (result.status === 'success') {
            currentCategories = result.categories;
            renderCategories();
        } else {
            showNotification(`Error loading categories: ${result.message}`, 'danger');
        }
    } catch (error) {
        console.error('Error loading categories:', error);
        showNotification('Error loading categories', 'danger');
    }
}

// Render categories in current view
function renderCategories() {
    if (currentView === 'grid') {
        renderCategoriesGrid();
    } else {
        renderCategoriesList();
    }
}

// Render categories as grid cards
function renderCategoriesGrid() {
    const container = document.getElementById('categories-grid');
    
    if (currentCategories.length === 0) {
        container.innerHTML = `
            <div class="col-12 text-center text-muted">
                <i class="fas fa-tags fa-3x mb-3"></i>
                <h5>No categories found</h5>
                <p>Create your first category to get started organizing your devices.</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = currentCategories.map(category => {
        const isDefault = category.is_default;
        const itemCount = 0; // TODO: Add item count from backend
        
        return `
            <div class="col-md-6 col-lg-4 mb-4">
                <div class="card h-100 category-card" style="border-left: 4px solid ${category.color};">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start mb-3">
                            <div class="category-icon" style="background-color: ${category.color}; color: white; width: 50px; height: 50px; border-radius: 50%; display: flex; align-items: center; justify-content: center;">
                                <i class="${category.icon} fa-lg"></i>
                            </div>
                            <div class="dropdown">
                                <button class="btn btn-sm btn-outline-secondary dropdown-toggle" type="button" data-bs-toggle="dropdown">
                                    <i class="fas fa-ellipsis-v"></i>
                                </button>
                                <ul class="dropdown-menu">
                                    ${!isDefault ? `
                                        <li><a class="dropdown-item" href="#" onclick="editCategory(${category.id})">
                                            <i class="fas fa-edit me-2"></i>Edit
                                        </a></li>
                                        <li><hr class="dropdown-divider"></li>
                                        <li><a class="dropdown-item text-danger" href="#" onclick="deleteCategory(${category.id}, '${category.name}')">
                                            <i class="fas fa-trash me-2"></i>Delete
                                        </a></li>
                                    ` : `
                                        <li><span class="dropdown-item-text text-muted">
                                            <i class="fas fa-lock me-2"></i>Default category
                                        </span></li>
                                    `}
                                </ul>
                            </div>
                        </div>
                        
                        <h5 class="card-title">${category.name}</h5>
                        
                        ${category.description ? `
                            <p class="card-text text-muted small">${category.description}</p>
                        ` : ''}
                        
                        <div class="d-flex justify-content-between align-items-center mt-auto">
                            <div>
                                <small class="text-muted">
                                    <i class="fas fa-box me-1"></i>${itemCount} items
                                </small>
                            </div>
                            <div>
                                ${isDefault ? `
                                    <span class="badge bg-primary">Default</span>
                                ` : `
                                    <span class="badge bg-secondary">Custom</span>
                                `}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

// Render categories as table list
function renderCategoriesList() {
    const tbody = document.getElementById('categories-table');
    
    if (currentCategories.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="text-center text-muted">
                    <i class="fas fa-tags fa-2x mb-2"></i>
                    <br>No categories found. Create your first category to get started.
                </td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = currentCategories.map(category => {
        const isDefault = category.is_default;
        const itemCount = 0; // TODO: Add item count from backend
        
        return `
            <tr>
                <td>
                    <div class="d-flex align-items-center">
                        <div class="category-icon me-3" style="background-color: ${category.color}; color: white; width: 35px; height: 35px; border-radius: 50%; display: flex; align-items: center; justify-content: center;">
                            <i class="${category.icon}"></i>
                        </div>
                        <div>
                            <strong>${category.name}</strong>
                        </div>
                    </div>
                </td>
                <td>
                    ${category.description ? `
                        <span class="text-muted">${category.description}</span>
                    ` : `
                        <span class="text-muted fst-italic">No description</span>
                    `}
                </td>
                <td>
                    ${isDefault ? `
                        <span class="badge bg-primary">Default</span>
                    ` : `
                        <span class="badge bg-secondary">Custom</span>
                    `}
                </td>
                <td>
                    <span class="text-muted">${itemCount}</span>
                </td>
                <td>
                    <small class="text-muted">${formatDate(category.created_at)}</small>
                </td>
                <td>
                    ${!isDefault ? `
                        <div class="btn-group" role="group">
                            <button class="btn btn-sm btn-outline-primary" onclick="editCategory(${category.id})" title="Edit category">
                                <i class="fas fa-edit"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-danger" onclick="deleteCategory(${category.id}, '${category.name}')" title="Delete category">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    ` : `
                        <span class="text-muted small">
                            <i class="fas fa-lock me-1"></i>Protected
                        </span>
                    `}
                </td>
            </tr>
        `;
    }).join('');
}

// Toggle between grid and list view
function toggleCategoryView(view) {
    currentView = view;
    
    const gridView = document.getElementById('categories-grid-view');
    const listView = document.getElementById('categories-list-view');
    
    if (view === 'grid') {
        gridView.style.display = 'block';
        listView.style.display = 'none';
        renderCategoriesGrid();
    } else {
        gridView.style.display = 'none';
        listView.style.display = 'block';
        renderCategoriesList();
    }
}

// Save new category
async function saveCategory() {
    const form = document.getElementById('addCategoryForm');
    const formData = new FormData(form);
    
    const categoryData = {
        name: formData.get('name').trim(),
        description: formData.get('description').trim(),
        icon: formData.get('icon'),
        color: formData.get('color')
    };
    
    // Validation
    if (!categoryData.name) {
        showNotification('Category name is required', 'warning');
        return;
    }
    
    if (categoryData.name.length < 2) {
        showNotification('Category name must be at least 2 characters', 'warning');
        return;
    }
    
    try {
        const response = await fetch('/api/categories', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(categoryData)
        });
        
        const result = await response.json();
        
        if (result.status === 'success') {
            showNotification('Category created successfully!', 'success');
            
            // Close modal and reset form
            const modal = bootstrap.Modal.getInstance(document.getElementById('addCategoryModal'));
            modal.hide();
            form.reset();
            
            // Reload categories
            await loadCategories();
        } else {
            showNotification(`Error: ${result.message}`, 'danger');
        }
        
    } catch (error) {
        console.error('Error saving category:', error);
        showNotification('Error saving category', 'danger');
    }
}

// Edit category
function editCategory(categoryId) {
    const category = currentCategories.find(c => c.id === categoryId);
    if (!category) {
        showNotification('Category not found', 'danger');
        return;
    }
    
    // Populate edit form
    document.getElementById('editCategoryId').value = category.id;
    document.getElementById('editCategoryName').value = category.name;
    document.getElementById('editCategoryDescription').value = category.description || '';
    document.getElementById('editCategoryIcon').value = category.icon;
    document.getElementById('editCategoryColor').value = category.color;
    
    // Update preview
    updateEditPreview();
    
    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('editCategoryModal'));
    modal.show();
}

// Update category
async function updateCategory() {
    const form = document.getElementById('editCategoryForm');
    const formData = new FormData(form);
    
    const categoryId = parseInt(formData.get('id'));
    const categoryData = {
        name: formData.get('name').trim(),
        description: formData.get('description').trim(),
        icon: formData.get('icon'),
        color: formData.get('color')
    };
    
    // Validation
    if (!categoryData.name) {
        showNotification('Category name is required', 'warning');
        return;
    }
    
    if (categoryData.name.length < 2) {
        showNotification('Category name must be at least 2 characters', 'warning');
        return;
    }
    
    try {
        const response = await fetch(`/api/categories/${categoryId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(categoryData)
        });
        
        const result = await response.json();
        
        if (result.status === 'success') {
            showNotification('Category updated successfully!', 'success');
            
            // Close modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('editCategoryModal'));
            modal.hide();
            
            // Reload categories
            await loadCategories();
        } else {
            showNotification(`Error: ${result.message}`, 'danger');
        }
        
    } catch (error) {
        console.error('Error updating category:', error);
        showNotification('Error updating category', 'danger');
    }
}

// Delete category
function deleteCategory(categoryId, categoryName) {
    document.getElementById('deleteCategoryId').value = categoryId;
    document.getElementById('deleteCategoryName').textContent = categoryName;
    
    const modal = new bootstrap.Modal(document.getElementById('deleteCategoryModal'));
    modal.show();
}

// Confirm delete category
async function confirmDeleteCategory() {
    const categoryId = parseInt(document.getElementById('deleteCategoryId').value);
    
    try {
        const response = await fetch(`/api/categories/${categoryId}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (result.status === 'success') {
            showNotification('Category deleted successfully!', 'success');
            
            // Close modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('deleteCategoryModal'));
            modal.hide();
            
            // Reload categories
            await loadCategories();
        } else {
            showNotification(`Error: ${result.message}`, 'danger');
        }
        
    } catch (error) {
        console.error('Error deleting category:', error);
        showNotification('Error deleting category', 'danger');
    }
}

// Update add modal preview
function updateAddPreview() {
    const preview = document.querySelector('.category-preview');
    const icon = document.getElementById('categoryIcon').value;
    const color = document.getElementById('categoryColor').value;
    const name = document.getElementById('categoryName').value || 'Preview';
    
    preview.style.backgroundColor = color;
    preview.innerHTML = `<i class="${icon} me-2"></i><span>${name}</span>`;
}

// Update edit modal preview
function updateEditPreview() {
    const preview = document.querySelector('.edit-category-preview');
    const icon = document.getElementById('editCategoryIcon').value;
    const color = document.getElementById('editCategoryColor').value;
    const name = document.getElementById('editCategoryName').value || 'Preview';
    
    preview.style.backgroundColor = color;
    preview.innerHTML = `<i class="${icon} me-2"></i><span>${name}</span>`;
}

// Format date helper
function formatDate(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleDateString();
}