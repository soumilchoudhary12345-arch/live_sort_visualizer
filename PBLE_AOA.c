#include <stdio.h>

#define MAX 100

struct Package {
    int id;
    float value, weight, ratio, fraction;
};

struct Package p[MAX];
int n = 0, entered = 0, sorted = 0;
float capacity = 0, totalValue = 0, totalWeight = 0;

void enterPackages() {
    printf("Enter number of packages (max %d): ", MAX);
    scanf("%d", &n);

    if (n <= 0 || n > MAX) {
        printf("Invalid number of packages!\n");
        n = 0;
        entered = sorted = 0;
        return;
    }

    for (int i = 0; i < n; i++) {
        p[i].id = i + 1;

        printf("Enter value of package %d: ", i + 1);
        scanf("%f", &p[i].value);

        printf("Enter weight of package %d: ", i + 1);
        scanf("%f", &p[i].weight);

        if (p[i].value < 0 || p[i].weight <= 0) {
            printf("Invalid value or weight! Try again.\n");
            i--;
            continue;
        }

        p[i].ratio = p[i].value / p[i].weight;
        p[i].fraction = 0;
    }

    printf("Enter vehicle capacity: ");
    scanf("%f", &capacity);

    if (capacity < 0) {
        printf("Invalid capacity!\n");
        n = 0;
        entered = sorted = 0;
        return;
    }

    entered = 1;
    sorted = 0;
    printf("Package details entered successfully!\n");
}

void displayPackages() {
    if (!entered) {
        printf("Enter package details first!\n");
        return;
    }

    printf("\nPackage\tValue\tWeight\tRatio\n");

    for (int i = 0; i < n; i++) {
        printf("%d\t%.2f\t%.2f\t%.2f\n",
               p[i].id, p[i].value,
               p[i].weight, p[i].ratio);
    }

    printf("Capacity: %.2f\n", capacity);
}

void calculateRatios() {
    if (!entered) {
        printf("Enter package details first!\n");
        return;
    }

    for (int i = 0; i < n; i++) {
        p[i].ratio = p[i].value / p[i].weight;
        printf("Package %d ratio = %.2f\n",
               p[i].id, p[i].ratio);
    }
}

void sortPackages() {
    if (!entered) {
        printf("Enter package details first!\n");
        return;
    }

    for (int i = 0; i < n - 1; i++) {
        for (int j = 0; j < n - i - 1; j++) {
            if (p[j].ratio < p[j + 1].ratio) {
                struct Package temp = p[j];
                p[j] = p[j + 1];
                p[j + 1] = temp;
            }
        }
    }

    sorted = 1;
    printf("Packages sorted by decreasing ratio.\n");
    displayPackages();
}

void findMaximumValue() {
    if (!entered || !sorted) {
        printf("Enter and sort packages first!\n");
        return;
    }

    float remaining = capacity;
    totalValue = totalWeight = 0;

    for (int i = 0; i < n; i++) {
        p[i].fraction = 0;

        if (remaining <= 0)
            break;

        if (p[i].weight <= remaining) {
            p[i].fraction = 1;
            totalValue += p[i].value;
            totalWeight += p[i].weight;
            remaining -= p[i].weight;
        } else {
            p[i].fraction = remaining / p[i].weight;
            totalValue += p[i].value * p[i].fraction;
            totalWeight += remaining;
            remaining = 0;
        }
    }

    printf("Total weight used: %.2f\n", totalWeight);
    printf("Maximum value: %.2f\n", totalValue);
}

void displaySelectedPackages() {
    if (!entered || !sorted) {
        printf("Enter and sort packages first!\n");
        return;
    }

    printf("\nPackage\tFraction\tWeight Taken\tValue Obtained\n");

    for (int i = 0; i < n; i++) {
        if (p[i].fraction > 0) {
            printf("%d\t%.2f\t\t%.2f\t\t%.2f\n",
                   p[i].id,
                   p[i].fraction,
                   p[i].weight * p[i].fraction,
                   p[i].value * p[i].fraction);
        }
    }

    printf("Total weight: %.2f\n", totalWeight);
    printf("Maximum value: %.2f\n", totalValue);
}

int main() {
    int choice;

    do {
        printf("\n===== SMART DELIVERY PLANNING =====\n");
        printf("1. Enter Package Details\n");
        printf("2. Display Package Details\n");
        printf("3. Calculate Value/Weight Ratio\n");
        printf("4. Sort Packages by Ratio\n");
        printf("5. Find Maximum Value\n");
        printf("6. Display Selected Packages\n");
        printf("7. Exit\n");
        printf("Enter your choice: ");
        scanf("%d", &choice);

        switch (choice) {
            case 1: enterPackages(); break;
            case 2: displayPackages(); break;
            case 3: calculateRatios(); break;
            case 4: sortPackages(); break;
            case 5: findMaximumValue(); break;
            case 6: displaySelectedPackages(); break;
            case 7: printf("Exiting program.\n"); break;
            default: printf("Invalid choice!\n");
        }
    } while (choice != 7);

    return 0;
}
