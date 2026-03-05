/**
 * Test3.java — Java port of test3.c
 * Same algorithms: dot_product, count_digits, matrix_trace, compare_points.
 * Used to validate cross-language clone detection with the C original.
 */
public class Test3 {

    static class Point {
        double x;
        double y;

        Point(double x, double y) {
            this.x = x;
            this.y = y;
        }
    }

    static double dot_product(double[] a, double[] b, int n) {
        double result = 0.0;
        for (int i = 0; i < n; i++) {
            result += a[i] * b[i];
        }
        return result;
    }

    static int count_digits(int n) {
        if (n == 0) {
            return 1;
        }
        int count = 0;
        while (n > 0) {
            count++;
            n = n / 10;
        }
        return count;
    }

    static double matrix_trace(double[][] mat, int n) {
        double trace = 0.0;
        for (int i = 0; i < n; i++) {
            trace += mat[i][i];
        }
        return trace;
    }

    static int compare_points(Point p1, Point p2) {
        double d1 = p1.x * p1.x + p1.y * p1.y;
        double d2 = p2.x * p2.x + p2.y * p2.y;
        if (d1 < d2) {
            return -1;
        }
        if (d1 > d2) {
            return 1;
        }
        return 0;
    }

    public static void main(String[] args) {
        double[] a = {1.0, 2.0, 3.0};
        double[] b = {4.0, 5.0, 6.0};
        double dp = dot_product(a, b, 3);
        System.out.println("dot_product: " + dp);

        int d0 = count_digits(0);
        int d1 = count_digits(9);
        int d5 = count_digits(12345);
        System.out.println("count_digits: " + d0 + " " + d1 + " " + d5);

        double[][] mat = {{1.0, 2.0, 3.0}, {4.0, 5.0, 6.0}, {7.0, 8.0, 9.0}};
        double tr = matrix_trace(mat, 3);
        System.out.println("matrix_trace: " + tr);

        Point p1 = new Point(1.0, 0.0);
        Point p2 = new Point(0.0, 2.0);
        int cmp = compare_points(p1, p2);
        System.out.println("compare_points: " + cmp);
    }
}